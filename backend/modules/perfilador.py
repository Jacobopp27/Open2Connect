"""Perfilador: agente de pre-registro que busca al asistente en la base de la
comunidad organizadora (simulación de la API de AI Tinkerers) y arma el
perfil de la app con lo que encuentra, marcando lo que falta para que el
check-in lo complete por voz.

Fuente de datos: tabla `community.profiles` en Supabase, vía la API REST
(PostgREST) de Supabase. Con SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY
presentes se consulta esa tabla por urllib (sin dependencias externas). Sin
esas variables, el módulo queda en modo local y usa COMMUNITY_DEMO (3
perfiles ficticios) para poder probar sin red.

# verificar: para que Accept-Profile: community funcione, el esquema
# "community" debe estar agregado en Supabase → Project Settings → API →
# Exposed schemas (por defecto solo "public" está expuesto).

Al terminar de construir el perfil, se registra el asistente en Ambiguous
(CRM) vía backend.modules.ambiguous.registrar_asistente — esa llamada es
best-effort y nunca rompe el flujo (ver backend/modules/ambiguous.py).
"""
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from backend.modules import ambiguous
from backend.modules import enriquecedor
from backend.modules.profiles import REQUIRED

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# Vocabulario cerrado de looking_for / help_with.
TAGS_AYUDA = [
    'backend', 'frontend', 'movil', 'diseno_ux', 'producto', 'datos_ml',
    'agentes_llm', 'voz', 'infra_devops', 'ventas_gtm', 'marketing',
    'financiacion', 'legal', 'mentoria', 'usuarios_pilotos', 'cofundador',
    'talento_empleo',
]

# Vocabulario cerrado de interests.
TAGS_INTERESES = [
    'agentes', 'voz', 'vision', 'educacion', 'salud', 'fintech', 'logistica',
    'eventos', 'gobierno', 'open_source', 'hardware_iot', 'creadores',
]

ETIQUETAS = {
    'backend': 'backend',
    'frontend': 'frontend',
    'movil': 'móvil',
    'diseno_ux': 'diseño / UX',
    'producto': 'producto',
    'datos_ml': 'datos / ML',
    'agentes_llm': 'agentes / LLM',
    'voz': 'voz',
    'infra_devops': 'infraestructura / DevOps',
    'ventas_gtm': 'ventas / GTM',
    'marketing': 'marketing',
    'financiacion': 'financiación',
    'legal': 'legal',
    'mentoria': 'mentoría',
    'usuarios_pilotos': 'usuarios piloto',
    'cofundador': 'cofundador/a',
    'talento_empleo': 'talento / empleo',
    'agentes': 'agentes',
    'vision': 'visión',
    'educacion': 'educación',
    'salud': 'salud',
    'fintech': 'fintech',
    'logistica': 'logística',
    'eventos': 'eventos',
    'gobierno': 'gobierno',
    'open_source': 'open source',
    'hardware_iot': 'hardware / IoT',
    'creadores': 'creadores',
}

# Perfiles ficticios para probar el módulo sin SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY.
COMMUNITY_DEMO = [
    {
        'id': 'demo-1',
        'full_name': 'Laura Gómez',
        'email': 'laura.gomez@example.com',
        'company': 'Datalia',
        'role': 'Head of Product',
        'seniority': 'senior',
        'city': 'Medellín',
        'languages': ['español', 'inglés'],
        'bio': 'Construyo productos de datos para pymes latinoamericanas.',
        'skills': ['product management', 'sql', 'analítica'],
        'interests': ['fintech', 'open_source'],
        'looking_for': ['cofundador', 'financiacion'],
        'help_with': ['producto', 'datos_ml'],
        'current_project': 'Un dashboard de analítica financiera para pymes',
        'linkedin_url': 'https://linkedin.com/in/lauragomez-demo',
    },
    {
        'id': 'demo-2',
        'full_name': 'Camilo Restrepo',
        'email': 'camilo.restrepo@example.com',
        'company': 'Vozia Labs',
        'role': 'ML Engineer',
        'seniority': 'mid',
        'city': 'Bogotá',
        'languages': ['español', 'inglés', 'portugués'],
        'bio': 'Trabajo en agentes de voz para atención al cliente.',
        'skills': ['python', 'nlp', 'pytorch'],
        'interests': ['agentes', 'voz'],
        'looking_for': ['usuarios_pilotos', 'mentoria'],
        'help_with': ['agentes_llm', 'voz'],
        'current_project': 'Un agente de voz para call centers en español',
        'linkedin_url': 'https://linkedin.com/in/camilorestrepo-demo',
    },
    {
        'id': 'demo-3',
        'full_name': 'Ana Torres',
        'email': 'ana.torres@example.com',
        'company': '',
        'role': 'Diseñadora UX freelance',
        'seniority': 'senior',
        'city': 'Cali',
        'languages': ['español'],
        'bio': 'Diseño experiencias para startups de salud digital.',
        'skills': ['figma', 'research', 'prototipado'],
        'interests': ['salud', 'educacion'],
        'looking_for': ['cofundador', 'talento_empleo'],
        'help_with': ['diseno_ux', 'mentoria'],
        'current_project': '',
        'linkedin_url': 'https://linkedin.com/in/anatorres-demo',
    },
]


def _consultar_supabase(query: str):
    """GET a la API REST de Supabase (esquema community.profiles). None si falla."""
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/profiles?{query}"
    req = urllib.request.Request(url, method='GET')
    req.add_header('apikey', SUPABASE_SERVICE_ROLE_KEY)
    req.add_header('Authorization', f'Bearer {SUPABASE_SERVICE_ROLE_KEY}')
    # verificar: requiere que "community" esté en Exposed schemas (Supabase → API settings).
    req.add_header('Accept-Profile', 'community')
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            body = resp.read()
            data = json.loads(body) if body else []
            return data if isinstance(data, list) else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        logging.warning('[perfilador] consulta a Supabase falló: %s', type(exc).__name__)
        return None


def buscar_en_comunidad(email: str = None, nombre: str = None) -> list:
    """Busca en la base de la comunidad por email (exacto) o nombre (parcial).

    Sin red configurada, busca en COMMUNITY_DEMO. Si la consulta remota falla
    o no hay coincidencias, devuelve lista vacía (el flujo de registro sigue).
    """
    if not email and not nombre:
        return []

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        if email:
            email_lower = email.lower()
            return [p for p in COMMUNITY_DEMO if p.get('email', '').lower() == email_lower]
        nombre_lower = nombre.lower()
        return [p for p in COMMUNITY_DEMO if nombre_lower in p.get('full_name', '').lower()]

    if email:
        query = f'select=*&email=eq.{urllib.parse.quote(email)}'
    else:
        query = f'select=*&full_name=ilike.*{urllib.parse.quote(nombre)}*'

    resultado = _consultar_supabase(query)
    return resultado if resultado is not None else []


def construir_perfil(comunidad: dict) -> dict:
    """Mapea un registro de community.profiles al esquema de perfil de la app."""
    interests_tags = comunidad.get('interests') or []
    help_with_tags = comunidad.get('help_with') or []
    looking_for_tags = comunidad.get('looking_for') or []
    skills_list = comunidad.get('skills') or []
    languages_list = comunidad.get('languages') or []

    interests_txt = ', '.join(ETIQUETAS.get(tag, tag) for tag in interests_tags)
    skills_txt = ', '.join(list(skills_list) + [ETIQUETAS.get(tag, tag) for tag in help_with_tags])
    help_txt = ', '.join(ETIQUETAS.get(tag, tag) for tag in looking_for_tags)
    languages_txt = ', '.join(languages_list)

    perfil = {
        'name': comunidad.get('full_name') or '',
        'role': comunidad.get('role') or '',
        'sector': comunidad.get('company') or '',
        'interests': interests_txt,
        'languages': languages_txt,
        'skills': skills_txt,
        'help': help_txt,
        'purpose': comunidad.get('current_project') or '',
        'problem': '',  # se pregunta en check-in
        'priority': 'medium',
        'availability': 'available',
        'contact': comunidad.get('email') or '',
        'share_contact': False,
    }

    fuentes = {campo: 'comunidad' for campo, valor in perfil.items() if campo != 'share_contact' and valor}
    faltantes = [campo for campo in REQUIRED if not perfil.get(campo)]

    perfil['fuentes'] = fuentes
    perfil['faltantes'] = faltantes
    perfil['tags'] = {
        'looking_for': list(looking_for_tags),
        'help_with': list(help_with_tags),
        'interests': list(interests_tags),
    }
    return perfil


def perfilar(email: str = None, nombre: str = None, event: str = 'medellin-2026', linkedin_url: str = None, consentimiento_web: bool = False) -> dict:
    """Busca al asistente, arma su perfil y lo registra en Ambiguous.

    - 0 resultados: {"encontrado": False, "perfil": None, "candidatos": []}.
      Si consentimiento_web es True, en vez de "perfil": None se busca a la
      persona en la web (backend.modules.enriquecedor, segunda fuente) y se
      devuelve {"encontrado": False, "perfil": {"name": nombre}, "web":
      resultado_enriquecedor, "sugerencias": help_with_sugeridos, "candidatos": []}.
    - >1 resultados: {"encontrado": False, "perfil": None, "candidatos": [...]}
      (para que el agente de voz desambigüe con la persona)
    - 1 resultado: construye el perfil, lo registra en Ambiguous y devuelve
      {"encontrado": True, "perfil": perfil}; si consentimiento_web es True
      se le adjunta "web" (misma búsqueda en enriquecedor) sin tocar el perfil.

    La búsqueda web solo ocurre con consentimiento_web=True (consentimiento
    explícito de la persona) y nunca en lote: una llamada por persona.
    """
    resultados = buscar_en_comunidad(email=email, nombre=nombre)

    if not resultados:
        if consentimiento_web:
            resultado_web = enriquecedor.buscar_publico(nombre or '', '', linkedin_url or '', True)
            sugerencias = resultado_web.get('help_with_sugeridos', []) if resultado_web.get('ok') else []
            return {
                'encontrado': False,
                'perfil': {'name': nombre or ''},
                'web': resultado_web,
                'sugerencias': sugerencias,
                'candidatos': [],
            }
        return {'encontrado': False, 'perfil': None, 'candidatos': []}

    if len(resultados) > 1:
        candidatos = [
            {'id': r.get('id'), 'nombre': r.get('full_name', ''), 'empresa': r.get('company', '')}
            for r in resultados
        ]
        return {'encontrado': False, 'perfil': None, 'candidatos': candidatos}

    perfil = construir_perfil(resultados[0])
    ambiguous.registrar_asistente(perfil, event)
    resultado = {'encontrado': True, 'perfil': perfil}
    if consentimiento_web:
        resultado['web'] = enriquecedor.buscar_publico(perfil.get('name', ''), perfil.get('sector', ''), linkedin_url or '', True)
    return resultado


def preguntas_pendientes(perfil: dict) -> list:
    """Preguntas en español que el check-in debe hacer según lo que falte."""
    preguntas = []
    if not perfil.get('problem'):
        preguntas.append('¿Qué vienes a resolver hoy?')
    if not perfil.get('help'):
        preguntas.append('¿Qué tipo de persona o ayuda buscas hoy?')
    if not perfil.get('skills'):
        preguntas.append('¿En qué le podrías ayudar a alguien esta tarde?')
    if not perfil.get('interests'):
        preguntas.append('¿Qué tema te tiene enganchado últimamente?')
    if not perfil.get('sena'):
        preguntas.append('¿Cómo te reconozco? ¿De qué color andas?')
    return preguntas


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print('=== Modo local (COMMUNITY_DEMO) ===\n')

    for demo in COMMUNITY_DEMO:
        resultado = perfilar(email=demo['email'])
        print(f"--- {demo['full_name']} ({demo['email']}) ---")
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        if resultado['encontrado']:
            print('Preguntas pendientes:')
            for pregunta in preguntas_pendientes(resultado['perfil']):
                print(f'  - {pregunta}')
        print()

    print('=== Desambiguación por nombre parcial ("a") ===\n')
    ambiguo = perfilar(nombre='a')
    print(json.dumps(ambiguo, ensure_ascii=False, indent=2))
    print()

    print('=== Sin resultados ===\n')
    sin_resultado = perfilar(email='nadie@example.com')
    print(json.dumps(sin_resultado, ensure_ascii=False, indent=2))
