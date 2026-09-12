"""Local MVP HTTP service. Deploy behind an HTTPS reverse proxy in production."""
import json
import logging
import os
import time
import threading
from collections import defaultdict, deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from backend.db import connect, initialize
from backend.modules.auth import Problem, authenticate, current_user
from backend.modules import profiles, conversation, matching, connections, notifications, events, interviews, mcp_access, kiosk, encuentros, agent

ROOT = Path(__file__).resolve().parent.parent / 'frontend'
FEATURES = {'voice': os.getenv('ENABLE_VOICE','1') == '1', 'connections': os.getenv('ENABLE_CONNECTIONS','1') == '1', 'demo': os.getenv('ENABLE_DEMO','1') == '1'}
COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME','session')
LIMITS = defaultdict(deque)
LIMIT_LOCK = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    server_version = 'Open2Connect'
    def log_message(self, fmt, *args):
        # Do not log request bodies, emails, or session tokens.
        logging.info('%s %s', self.command, urlparse(self.path).path)
    def send(self, status, data, cookie=None, content_type='application/json; charset=utf-8'):
        body = json.dumps(data, ensure_ascii=False).encode() if content_type.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self' https://api.openai.com; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)
    def token(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie',''))
            return cookies[COOKIE_NAME].value if COOKIE_NAME in cookies else ''
        except Exception:
            return ''
    def cookie(self, token, age=604800):
        return f'{COOKIE_NAME}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={age}' + ('; Secure' if os.getenv('COOKIE_SECURE') == '1' else '')
    def body(self):
        # A non-simple custom header plus no CORS prevents cross-site POSTs.
        if self.headers.get('X-Open2Connect') != '1' or self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            raise Problem('Solicitud no permitida. / Request not allowed.',403)
        origin = self.headers.get('Origin')
        allowed = os.getenv('APP_ORIGIN')
        if origin and ((allowed and origin != allowed) or (not allowed and urlparse(origin).netloc != self.headers.get('Host'))):
            raise Problem('Origen no permitido. / Origin not allowed.',403)
        try:
            size = int(self.headers.get('Content-Length','0'))
            # La foto para la seña (base64) pesa más de 40 KB; solo esa ruta admite hasta 2 MB.
            limite = 2_000_000 if urlparse(self.path).path == '/api/agent/apariencia' else 40000
            if size < 0 or size > limite:
                raise Problem('Solicitud demasiado grande. / Request too large.',413)
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError()
            return payload
        except (ValueError, json.JSONDecodeError):
            raise Problem('JSON inválido. / Invalid JSON.')
    def do_GET(self):
        self.handle_request(False)
    def do_POST(self):
        self.handle_request(True)
    def handle_request(self, post):
        try:
            path = urlparse(self.path).path
            query = parse_qs(urlparse(self.path).query)
            event = query.get('event',['medellin-2026'])[0]
            if not path.startswith('/api/'):
                if post:
                    raise Problem('Not found',404)
                files = {'/':('index.html','text/html; charset=utf-8'), '/app.js':('app.js','text/javascript; charset=utf-8'), '/styles.css':('styles.css','text/css; charset=utf-8'), '/speech.js':('speech.js','text/javascript; charset=utf-8'),
                         '/realtime.js':('realtime.js','text/javascript; charset=utf-8'), '/agent.js':('agent.js','text/javascript; charset=utf-8'), '/agent.css':('agent.css','text/css; charset=utf-8'),
                         '/qr.js':('qr.js','text/javascript; charset=utf-8'),
                         '/yo.js':('yo.js','text/javascript; charset=utf-8'), '/yo.css':('yo.css','text/css; charset=utf-8')}
                if path.startswith('/yo/'):
                    # HTML público; las API exigen sesión del propietario.
                    return self.send(200,(ROOT/'yo.html').read_bytes(),content_type='text/html; charset=utf-8')
                if path in ('/kiosk', '/interview', '/interviews'):
                    self.send_response(302)
                    self.send_header('Location', '/agent')
                    self.send_header('Content-Length','0')
                    self.end_headers()
                    return
                if path == '/agent':
                    return self.send(200, (ROOT/'agent.html').read_bytes(), content_type='text/html; charset=utf-8')
                if path not in files:
                    raise Problem('Not found',404)
                name, content_type = files[path]
                return self.send(200,(ROOT/name).read_bytes(),content_type=content_type)
            payload = self.body() if post else {}
            if path == '/api/config' and not post:
                from backend.adapters.profile_store import status
                return self.send(200,{'features':FEATURES,'extraction':'rules-v1','interview':agent.status(),'storage':status()})
            if path == '/api/health' and not post:
                return self.send(200,{'status':'ok'})
            if path in ('/api/register','/api/login') and post:
                with LIMIT_LOCK:
                    now = time.time()
                    attempts = LIMITS[self.client_address[0]]
                    while attempts and attempts[0] < now - 60:
                        attempts.popleft()
                    if len(attempts) >= 15:
                        raise Problem('Demasiados intentos; espera un minuto. / Too many attempts; wait a minute.',429)
                    attempts.append(now)
                return self.send(200,{'ok':True},self.cookie(authenticate(payload,path == '/api/register')))
            bearer = self.headers.get('Authorization','')
            if bearer:
                if not bearer.startswith('Bearer '): raise Problem('Invalid authorization',401)
                user = mcp_access.authenticate(bearer[7:],path,post)
                if 'event' in query and event != user['mcp_event']: raise Problem('Evento fuera del alcance MCP. / Event outside MCP scope.',403)
                event = user['mcp_event']
            else:
                user = current_user(self.token())
            if path.startswith('/api/agent/') and post:
                return self.send(200,agent.handle(user,event,path.rsplit('/',1)[-1],payload))
            if path in ('/api/yo/estado','/api/yo/confirmar'):
                requested = payload.get('id') if post else query.get('id',[''])[0]
                if requested and requested != user['id']:
                    raise Problem('Esta página pertenece a otro participante.',403)
                if path == '/api/yo/estado' and not post:
                    return self.send(200,encuentros.estado(user['id'],event))
                if path == '/api/yo/confirmar' and post:
                    return self.send(200,encuentros.confirmar(user['id'],str(payload.get('otro','')),event))
            if path == '/api/mcp/token' and post:
                return self.send(200,mcp_access.mint(user,event,self.token()))
            if path == '/api/mcp/revoke' and post:
                return self.send(200,mcp_access.revoke(user))
            if path == '/api/interviews/start' and post:
                return self.send(200,interviews.start(user,event,payload))
            if path == '/api/interviews/draft' and not post:
                return self.send(200,interviews.get(user,query.get('id',[''])[0]))
            if path.startswith('/api/interviews/') and post:
                action = path.rsplit('/',1)[-1]
                handler = {'turn':interviews.turn,'edit':interviews.edit_draft,'summary':interviews.summary,'confirm':interviews.confirm,'control':interviews.control}.get(action)
                if handler: return self.send(200,handler(user,payload))
            if path == '/api/me' and not post:
                return self.send(200,{'id':user['id'],'email':user['email']})
            if path == '/api/logout' and post:
                with connect() as db:
                    db.execute('DELETE FROM sessions WHERE token=?',(self.token(),))
                return self.send(200,{'ok':True},self.cookie('',0))
            if path == '/api/events' and not post:
                return self.send(200,events.events())
            if path == '/api/profile':
                if not post:
                    return self.send(200, profiles.get_profile(user,event))
                resultado = profiles.save_profile(user,event,payload)
                # Perfilado en segundo plano (comunidad + Ambiguous). Best-effort: nunca bloquea ni rompe el guardado.
                perfil_guardado = {**(payload.get('profile') or {}), 'email': user['email']}
                if os.getenv('ENABLE_EXTERNAL_SYNC') == '1':
                    threading.Thread(target=_perfilar_en_segundo_plano, args=(user['email'], perfil_guardado, event), daemon=True).start()
                return self.send(200, resultado)
            if path == '/api/conversation' and post:
                return self.send(200,conversation.converse(payload))
            if path == '/api/recommendations' and not post:
                return self.send(200,matching.recommendations(user,event))
            if path == '/api/demo' and post and FEATURES['demo']:
                return self.send(200,events.seed_demo())
            if path == '/api/block' and post:
                return self.send(200,connections.block(user,str(payload.get('target',''))))
            if path == '/api/notifications' and not post:
                return self.send(200,notifications.list_notifications(user))
            if path.startswith('/api/connections') and FEATURES['connections']:
                if path == '/api/connections' and not post:
                    return self.send(200,connections.connections(user,event))
                if path == '/api/connections/invite' and post:
                    return self.send(200,connections.invite(user,event,str(payload.get('target',''))))
                if path == '/api/connections/respond' and post:
                    return self.send(200,connections.respond(user,str(payload.get('id','')),payload.get('action')))
            raise Problem('Ruta no disponible. / Route unavailable.',404)
        except Problem as exc:
            self.send(exc.status, {'error':exc.message})
        except Exception:
            logging.exception('Request failed')
            self.send(500,{'error':'Error interno. Intenta de nuevo. / Internal error. Try again.'})

def _perfilar_en_segundo_plano(email, perfil, event):
    """Tras guardar un perfil confirmado: busca a la persona en la base de la comunidad y la registra en Ambiguous."""
    try:
        from backend.modules import perfilador, ambiguous
        resultado = perfilador.perfilar(email=email, nombre=perfil.get('name', ''), event=event)
        if not resultado.get('encontrado'):
            ambiguous.registrar_asistente(perfil, event)
    except Exception:
        logging.exception('perfilado en segundo plano falló')

def run():
    initialize()
    host, port = os.getenv('HOST','127.0.0.1'), int(os.getenv('PORT','8000'))
    server = ThreadingHTTPServer((host,port),Handler)
    print(f'Open2Connect → http://{host}:{port}',flush=True)
    server.serve_forever()

if __name__ == '__main__':
    run()
