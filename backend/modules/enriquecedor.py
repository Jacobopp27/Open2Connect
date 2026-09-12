"""Enriquecedor: segunda fuente de datos del Perfilador, con consentimiento.

Cuando la persona no está en la base de la comunidad (backend/modules/
perfilador.py) o cuando dio su URL de LinkedIn, este módulo busca
información PÚBLICA sobre ella en la web usando la API de Exa
(https://api.exa.ai) — nunca hace scraping directo de LinkedIn ni de
ninguna otra página. Se usa persona por persona, nunca en lote, y solo si
la persona dio su consentimiento explícito (parámetro `consentimiento`).

Con EXA_API_KEY presente se hacen hasta 2 llamadas HTTP (timeout 3 s cada
una) por urllib, sin dependencias externas. Sin la llave, el módulo queda
en modo local: no llama a la red y responde {"ok": False, "motivo":
"sin_llave"}. En ningún caso lanza excepción hacia quien lo llama.

Nada de lo que este módulo sugiere (help_with_sugeridos) se guarda en el
perfil directamente: viene marcado con sugerido_por_web=True para que el
check-in por voz se lo confirme a la persona antes de guardarlo (mismo
principio que perfilador.py usa con `faltantes`).

# verificar: el formato de /search y /contents de abajo (nombres de
# parámetros, "type": "auto", forma de la respuesta) sigue la
# especificación dada al construir este módulo; no se probó contra la API
# real de Exa. Antes de usarlo en producción, confirmar contra
# https://docs.exa.ai que los campos y el status code de error coinciden.
"""
import json
import logging
import os
import re
import urllib.error
import urllib.request

BASE_URL = 'https://api.exa.ai/'
EXA_API_KEY = os.getenv('EXA_API_KEY')

# Mismo vocabulario cerrado de help_with que backend/modules/perfilador.py
# (TAGS_AYUDA), para que lo sugerido aquí sea compatible con el perfil.
TAGS_AYUDA = [
    'backend', 'frontend', 'movil', 'diseno_ux', 'producto', 'datos_ml',
    'agentes_llm', 'voz', 'infra_devops', 'ventas_gtm', 'marketing',
    'financiacion', 'legal', 'mentoria', 'usuarios_pilotos', 'cofundador',
    'talento_empleo',
]

# Sinónimos en español/inglés usados para detectar cada tag en texto libre
# (sin LLM: simple substring match sobre el texto en minúsculas).
SINONIMOS = {
    'backend': ['backend', 'back-end', 'servidor', 'api rest', 'django', 'node.js'],
    'frontend': ['frontend', 'front-end', 'react', 'vue', 'angular', 'interfaz web'],
    'movil': ['móvil', 'movil', 'mobile', 'ios', 'android', 'flutter', 'app móvil'],
    'diseno_ux': ['diseño', 'diseno', 'design', 'ux', 'ui/ux', 'figma', 'diseñadora', 'diseñador'],
    'producto': ['producto', 'product manager', 'product owner', 'head of product'],
    'datos_ml': ['datos', 'data science', 'machine learning', 'inteligencia artificial', ' ia ', 'analítica'],
    'agentes_llm': ['agentes', 'agents', 'llm', 'gpt', 'chatbot', 'modelos de lenguaje'],
    'voz': ['voz', 'voice', 'speech', 'audio conversacional'],
    'infra_devops': ['infraestructura', 'devops', 'cloud', 'aws', 'kubernetes', 'docker'],
    'ventas_gtm': ['ventas', 'sales', 'go-to-market', 'gtm', 'comercial'],
    'marketing': ['marketing', 'growth', 'publicidad'],
    'financiacion': ['inversión', 'inversion', 'investment', 'funding', 'venture capital', 'levantar capital'],
    'legal': ['legal', 'jurídico', 'juridico', 'abogado', 'abogada'],
    'mentoria': ['mentoría', 'mentoria', 'mentor', 'mentorship', 'coaching'],
    'usuarios_pilotos': ['usuarios piloto', 'pilot users', 'beta testers', 'programa piloto'],
    'cofundador': ['cofundador', 'cofundadora', 'co-founder', 'cofounder', 'socio fundador'],
    'talento_empleo': ['talento', 'contratación', 'contratacion', 'hiring', 'recruiting', 'empleo'],
}

# Palabras clave usadas solo para elegir la segunda frase del resumen
# heurístico (vocabulario "de superficie", tal como aparece en texto libre).
PALABRAS_CLAVE_RESUMEN = [
    'backend', 'frontend', 'diseño', 'diseno', 'producto', 'datos',
    'agentes', 'voz', 'ventas', 'marketing', 'inversión', 'inversion',
    'legal', 'mentoría', 'mentoria',
]


def _request(path: str, payload: dict, timeout: float = 3.0):
    """POST a la API de Exa. Devuelve el JSON decodificado o None si falla."""
    url = BASE_URL + path.lstrip('/')
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('x-api-key', EXA_API_KEY)
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return json.loads(body) if body else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        logging.warning('[enriquecedor] POST %s -> %s', path, type(exc).__name__)
        return None


def _ordenar_por_nombre(resultados: list, nombre: str) -> list:
    """Prioriza resultados cuyo título o URL contengan las palabras del nombre."""
    tokens = [t for t in re.findall(r'[a-záéíóúñ]+', (nombre or '').lower()) if len(t) > 2]
    def puntaje(r):
        base = ((r.get('title') or '') + ' ' + (r.get('url') or '')).lower()
        return sum(1 for t in tokens if t in base)
    return sorted(resultados, key=puntaje, reverse=True)


def _buscar_exa(query: str, include_domains: list = None, category: str = None):
    """POST /search. Formato confirmado con la guía oficial de Exa (sept 2026)."""
    payload = {
        'query': query,
        'type': 'auto',
        'numResults': 3,
        'contents': {'highlights': True, 'text': {'maxCharacters': 1500}},
    }
    if include_domains:
        payload['includeDomains'] = include_domains
    if category:
        payload['category'] = category  # "people": solo acepta includeDomains de LinkedIn
    data = _request('search', payload)
    if isinstance(data, dict):
        return data.get('results') or []
    return []


def _contents_exa(url: str):
    """POST /contents para una URL concreta (p. ej. un perfil de LinkedIn dado por la persona)."""
    payload = {'urls': [url], 'text': {'maxCharacters': 2000}}
    data = _request('contents', payload)
    if isinstance(data, dict):
        resultados = data.get('results')
        return resultados if isinstance(resultados, list) else []
    return None


def _dividir_frases(texto: str) -> list:
    frases = re.split(r'(?<=[.!?])\s+|\n+', texto)
    return [f.strip() for f in frases if f.strip()]


def _sugerir_help_with(texto: str) -> list:
    """Lista de tags de TAGS_AYUDA cuyos sinónimos aparecen en el texto. Sin LLM."""
    texto_low = texto.lower()
    sugeridos = []
    for tag in TAGS_AYUDA:
        for sinonimo in SINONIMOS.get(tag, []):
            if sinonimo in texto_low:
                sugeridos.append(tag)
                break
    return sugeridos


def _resumir(texto: str, nombre: str, empresa: str) -> tuple:
    """Resumen heurístico de 2 líneas (sin LLM) + tags de ayuda sugeridos."""
    if not texto:
        return '', []

    frases = _dividir_frases(texto)
    terminos_persona = [t for t in (nombre, empresa) if t]

    primera = ''
    for frase in frases:
        frase_low = frase.lower()
        if any(t.lower() in frase_low for t in terminos_persona):
            primera = frase
            break
    if not primera and frases:
        primera = frases[0]

    segunda = ''
    for frase in frases:
        if frase == primera:
            continue
        frase_low = frase.lower()
        if any(palabra in frase_low for palabra in PALABRAS_CLAVE_RESUMEN):
            segunda = frase
            break

    resumen = '\n'.join(linea for linea in (primera, segunda) if linea)
    return resumen, _sugerir_help_with(texto)


def buscar_publico(nombre: str, empresa: str = '', linkedin_url: str = '', consentimiento: bool = False) -> dict:
    """Busca información pública de una persona (una a la vez, con su consentimiento).

    - Sin consentimiento: no llama a nada, {"ok": False, "motivo": "sin_consentimiento"}.
    - Sin EXA_API_KEY: modo local, {"ok": False, "motivo": "sin_llave"}.
    - Con linkedin_url: una llamada a /contents con esa URL.
    - Sin linkedin_url: /search con includeDomains ["linkedin.com"] (category people);
      si no hay resultados, una segunda /search sin includeDomains.
      Máximo 2 llamadas HTTP, timeout 3 s cada una.
    """
    if not consentimiento:
        return {'ok': False, 'motivo': 'sin_consentimiento'}

    if not EXA_API_KEY:
        logging.info('[enriquecedor:local] búsqueda pública omitida (sin EXA_API_KEY): %s', nombre)
        return {'ok': False, 'motivo': 'sin_llave'}

    if linkedin_url:
        resultados = _contents_exa(linkedin_url)
    else:
        query = f'{nombre} {empresa}'.strip()
        resultados = _ordenar_por_nombre(_buscar_exa(query, include_domains=['linkedin.com'], category='people'), nombre)
        if not resultados:
            resultados = _ordenar_por_nombre(_buscar_exa(query), nombre)

    if not resultados:
        return {'ok': False, 'motivo': 'sin_resultados', 'fuentes': [], 'texto': '', 'resumen': ''}

    fuentes = [{'titulo': r.get('title') or '', 'url': r.get('url') or ''} for r in resultados]
    texto = ' '.join((r.get('text') or '') for r in resultados).strip()[:1500]
    resumen, help_with_sugeridos = _resumir(texto, nombre, empresa)

    return {
        'ok': True,
        'fuentes': fuentes,
        'texto': texto,
        'resumen': resumen,
        'help_with_sugeridos': help_with_sugeridos,
        'sugerido_por_web': True,  # el check-in debe CONFIRMAR esto con la persona antes de guardarlo
    }


def desambiguar(nombre: str, candidatos_comunidad: list, texto_web: str) -> list:
    """Reordena candidatos de la comunidad según cuántos de sus datos aparecen en texto_web.

    Heurística sin LLM: cuenta coincidencias de empresa/rol de cada candidato
    (acepta tanto el registro completo de community.profiles como el resumen
    {"id","nombre","empresa"} que arma perfilador.perfilar) dentro del texto
    encontrado en la web. No cambia el orden si no hay texto_web o candidatos.
    """
    if not candidatos_comunidad or not texto_web:
        return candidatos_comunidad

    texto_low = texto_web.lower()

    def puntaje(candidato: dict) -> int:
        campos = [
            candidato.get('company') or candidato.get('empresa') or '',
            candidato.get('role') or candidato.get('rol') or '',
        ]
        return sum(1 for campo in campos if campo and campo.lower() in texto_low)

    return sorted(candidatos_comunidad, key=puntaje, reverse=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print('=== Sin consentimiento ===\n')
    print(json.dumps(buscar_publico('Laura Gómez', 'Datalia'), ensure_ascii=False, indent=2))
    print()

    print('=== Con consentimiento, modo local (sin EXA_API_KEY) ===\n')
    print(json.dumps(buscar_publico('Laura Gómez', 'Datalia', consentimiento=True), ensure_ascii=False, indent=2))
    print()

    print('=== Desambiguación heurística (sin llamada a red) ===\n')
    candidatos = [
        {'id': 'demo-1', 'nombre': 'Laura Gómez', 'empresa': 'Datalia'},
        {'id': 'demo-2', 'nombre': 'Camilo Restrepo', 'empresa': 'Vozia Labs'},
    ]
    texto_web = 'Camilo Restrepo trabaja en Vozia Labs construyendo agentes de voz para call centers.'
    print(json.dumps(desambiguar('Camilo', candidatos, texto_web), ensure_ascii=False, indent=2))
