"""Siembra 4 personas de demo (y 3 check-ins) en un despliegue de Open2Connect.
Uso: python3 scripts/seed_demo.py [https://open2connect.onrender.com]
Render borra la SQLite en cada deploy: correr después de cada push."""
import json, sys, time, urllib.request, urllib.error, http.cookiejar
B = (sys.argv[1] if len(sys.argv) > 1 else 'https://open2connect.onrender.com').rstrip('/')
EVENT = 'medellin-2026'; PASS = 'PruebaHackaton2026!'
BASE = dict(languages='español, inglés', priority='high', availability='available', share_contact=True, visible=True, knowledge='', services='', resources='', experience='')
PERSONAS = [
  dict(email='jacobo.demo@example.invalid', sena=None, profile=dict(BASE, name='Jacobo Posada', role='CTO · Kotiza', purpose='Encontrar diseño UX para Kotiza', problem='Necesito diseño UX para la app de cotizaciones por voz', help='diseño ux', outcome='Un diseñador con quien iterar', skills='backend, agentes de voz, python', interests='agentes, voz, startups', sector='software', contact='jacobo.demo@example.invalid')),
  dict(email='ana.demo@example.invalid', sena='camisa negra', profile=dict(BASE, name='Ana Prueba', role='Diseñadora de producto', purpose='Conocer equipos que necesiten diseño', problem='Necesito alguien de backend para mi side project', help='backend', outcome='Un cofundador técnico', skills='diseño ux, figma, research', interests='agentes, producto, startups', sector='diseño', contact='ana.demo@example.invalid')),
  dict(email='carlos.demo@example.invalid', sena='chaqueta azul', profile=dict(BASE, name='Carlos Ríos', role='Ventas B2B', purpose='Buscar producto para vender', problem='Necesito un producto de IA para ofrecer a pymes', help='producto', outcome='Alianza comercial', skills='ventas, negociación, pymes', interests='ventas, ia aplicada', sector='comercial', contact='carlos.demo@example.invalid')),
  dict(email='laura.demo@example.invalid', sena='gorra blanca', profile=dict(BASE, name='Laura Gil', role='Product manager', purpose='Validar una idea de agente', problem='Necesito canal de ventas para mi producto', help='ventas', outcome='Primeros clientes', skills='producto, roadmap, analítica', interests='agentes, ventas, producto', sector='producto', contact='laura.demo@example.invalid')),
]
def call(op, path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(B + path, data=data, method=method or ('POST' if data else 'GET'))
    r.add_header('Content-Type', 'application/json'); r.add_header('X-Open2Connect', '1'); r.add_header('Origin', B)
    try:
        with op.open(r, timeout=40) as x: return x.status, json.loads(x.read() or b'{}')
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b'{}')
for p in PERSONAS:
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    st, _ = call(op, '/api/register', {'email': p['email'], 'password': PASS})
    if st != 200: st, _ = call(op, '/api/login', {'email': p['email'], 'password': PASS})
    assert st == 200, (p['email'], st)
    st, r = call(op, f'/api/profile?event={EVENT}', {'confirmed': True, 'profile': p['profile']}); assert st == 200, (p['email'], st, r)
    st, r = call(op, '/api/kiosk/buscar', {'nombre': p['profile']['name']}); pid = r['resultados'][0]['id']
    if p['sena']:
        st, r = call(op, '/api/kiosk/checkin', {'id': pid, 'sena': p['sena']}); assert st == 200, r
    print(f"{p['profile']['name']:15} id={pid} {'check-in ✓ ('+p['sena']+')' if p['sena'] else 'sin check-in'}  página: {B}/yo/{pid}")
    time.sleep(0.3)
