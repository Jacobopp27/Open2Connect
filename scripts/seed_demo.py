"""Siembra 13 personas de demo (10 con check-in) en un despliegue de Open2Connect.
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
  dict(email='juan.demo@example.invalid', sena='camiseta blanca y lentes', profile=dict(BASE, name='Juan F. Villa', role='Data engineer', purpose='Conectar con gente de datos y agentes', problem='Necesito un frontend para un dashboard de comunidad', help='frontend', outcome='Prototipo visible', skills='python, datos, apis, sql', interests='agentes, datos, comunidades', sector='datos', contact='juan.demo@example.invalid')),
  dict(email='luis.demo@example.invalid', sena='buzo gris', profile=dict(BASE, name='Luis Saldarriaga', role='Full-stack developer', purpose='Buscar proyecto con tracción', problem='Necesito usuarios para probar una app de eventos', help='usuarios, comunidad', outcome='Feedback real de 20 personas', skills='javascript, python, supabase', interests='agentes, producto, eventos', sector='software', contact='luis.demo@example.invalid')),
  dict(email='mariana.demo@example.invalid', sena='vestido verde', profile=dict(BASE, name='Mariana López', role='Fundadora · edtech', purpose='Encontrar cofundador técnico', problem='Necesito backend y agentes de voz para tutorías', help='backend, agentes de voz', outcome='MVP en un mes', skills='pedagogía, ventas, producto', interests='educación, voz, agentes', sector='educación', contact='mariana.demo@example.invalid')),
  dict(email='santiago.demo@example.invalid', sena='camisa a cuadros', profile=dict(BASE, name='Santiago Mejía', role='Inversionista ángel', purpose='Conocer equipos early stage en IA', problem='Necesito deal flow de agentes B2B en LATAM', help='startups b2b, deal flow', outcome='Dos reuniones de seguimiento', skills='inversión, finanzas, mentoría', interests='agentes, b2b, fintech', sector='inversión', contact='santiago.demo@example.invalid')),
  dict(email='valentina.demo@example.invalid', sena='chaqueta amarilla', profile=dict(BASE, name='Valentina Ruiz', role='UX researcher', purpose='Colaborar con equipos que validen con usuarios', problem='Necesito un equipo técnico para aplicar research', help='equipo técnico, backend', outcome='Un proyecto para el portafolio', skills='diseño ux, research, prototipado', interests='producto, voz, accesibilidad', sector='diseño', contact='valentina.demo@example.invalid')),
  dict(email='andres.demo@example.invalid', sena='gorra negra', profile=dict(BASE, name='Andrés Cardona', role='ML engineer', purpose='Aprender de despliegues reales de agentes', problem='Necesito casos de uso reales para un modelo de voz', help='casos de uso, clientes', outcome='Un piloto', skills='machine learning, python, modelos de voz', interests='voz, agentes, open source', sector='ia', contact='andres.demo@example.invalid')),
  dict(email='camila.demo@example.invalid', sena='saco rojo', profile=dict(BASE, name='Camila Torres', role='Marketing B2B', purpose='Encontrar producto para lanzar', problem='Necesito un producto de IA con demo lista para hacerle contenido', help='producto, demo', outcome='Una campaña de lanzamiento', skills='marketing, contenido, video, ventas', interests='ventas, contenido, agentes', sector='marketing', contact='camila.demo@example.invalid')),
  dict(email='daniel.demo@example.invalid', sena=None, profile=dict(BASE, name='Daniel Ospina', role='Estudiante de ingeniería', purpose='Conseguir práctica en IA', problem='Necesito mentoría y un proyecto real', help='mentoría, proyecto', outcome='Una práctica', skills='python, javascript', interests='agentes, aprendizaje', sector='educación', contact='daniel.demo@example.invalid')),
  dict(email='paula.demo@example.invalid', sena=None, profile=dict(BASE, name='Paula Restrepo', role='Organizadora de comunidad', purpose='Mejorar el networking de nuestros eventos', problem='Necesito una herramienta de check-in y matching para eventos', help='check-in, matching, eventos', outcome='Probarla en el próximo meetup', skills='eventos, comunidad, alianzas', interests='comunidades, eventos, agentes', sector='comunidad', contact='paula.demo@example.invalid')),
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
    st, r = call(op, '/api/kiosk/buscar', {'nombre': p['profile']['name'], 'email': p['email']}); pid = r['resultados'][0]['id']  # por email: una sola coincidencia
    if p['sena']:
        st, r = call(op, '/api/kiosk/checkin', {'id': pid, 'sena': p['sena']}); assert st == 200, r
    print(f"{p['profile']['name']:15} id={pid} {'check-in ✓ ('+p['sena']+')' if p['sena'] else 'sin check-in'}  página: {B}/yo/{pid}")
    time.sleep(0.3)
