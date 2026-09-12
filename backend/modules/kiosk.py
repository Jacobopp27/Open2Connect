"""Kiosco de check-in por voz "Mesa 4" — Realtime API de OpenAI.

Arquitectura: WebRTC directo entre el navegador del kiosco y OpenAI. Este
módulo solo (a) crea el token efímero de sesión Realtime con las
instrucciones y tools del agente, y (b) implementa en Python lo que esas
tools hacen cuando el NAVEGADOR las invoca vía rutas HTTP del servidor (ver
el parche sugerido para backend/server.py en docs/KIOSK.md). El audio nunca
pasa por este servidor.

Sin dependencias externas: solo stdlib (urllib) y backend.db/backend.modules
existentes. No cambia el esquema de `profiles`/`users`; agrega una tabla
nueva `checkins` para la llegada física al evento.
"""
import difflib
import json
import os
import socket
import time
import unicodedata
import urllib.error
import urllib.request
from backend.db import connect
from backend.modules.auth import Problem
from backend.modules.matching import terms
from backend.modules import ambiguous

EVENT = 'medellin-2026'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

with connect() as _db:
    _db.execute('''CREATE TABLE IF NOT EXISTS checkins (
      user_id TEXT PRIMARY KEY REFERENCES users(id),
      event_id TEXT NOT NULL, checked_in_at REAL NOT NULL, sena TEXT NOT NULL)''')

INSTRUCCIONES = '''Eres "Mesa 4", la anfitriona de voz del registro de Open2Connect en Medellín. Hablas español colombiano, cálido y natural, como alguien de logística del evento — nunca como si leyeras un formulario.

Reglas duras:
- Una sola frase corta por turno. Nunca hagas varias preguntas seguidas.
- Nunca inventes ni asumas datos de la persona; si no lo dijo, pregúntalo.
- Nunca repitas una pregunta cuya respuesta ya tienes (del perfil o de lo que ya dijo en esta conversación).
- Antes de usar la seña de la persona para presentarla a otros, pide su permiso explícito.

Flujo:
1. Saluda en una sola frase y pregunta el nombre de la persona.
2. Repite el nombre que entendiste y pide confirmación en una sola frase, por ejemplo "¿Jacobo, así?". Si la persona corrige, usa siempre la corrección, no lo que dijo antes. Si el nombre te suena raro, incompleto o dudoso, pídele que lo deletree o que diga también el apellido, antes de seguir.
3. Solo cuando el nombre esté confirmado, pregunta si ya se registró al evento (si llenó su perfil en la web).
4. Si dice que NO: llama a mostrar_qr_registro, di en una sola frase que escanee el QR (o abra el enlace) para registrarse en un minuto, y despídete con calidez. No sigas el flujo.
5. Si dice que SÍ: llama a buscar_persona con el nombre confirmado (y el email si lo dio).
   - Si hay varios resultados, desambigua con una pregunta como "¿eres [nombre] de [rol o sector]?" hasta confirmar cuál es.
   - Si NO hay resultados, todavía no la mandes al QR: pregunta UNA sola vez "¿con qué correo te registraste?" o "¿cómo se escribe tu nombre?", y vuelve a llamar a buscar_persona con ese dato nuevo.
   - Si después de ese segundo intento sigue sin aparecer, ahí sí ofrécele el QR de registro (mostrar_qr_registro).
6. Con la persona encontrada, confirma en una frase lo que ya sabes de su perfil (su rol, qué busca, qué ofrece); pregunta solo lo que falte, una cosa a la vez: qué viene a resolver hoy en el evento y en qué puede ayudar a otros hoy. Luego pídele permiso para anotar una seña con la que otros puedan reconocerla, preguntando algo como "¿de qué color andas?".
   - Guarda cada respuesta con confirmar_perfil apenas la tengas, sin esperar a tener todo; solo llama a confirmar_perfil si hubo cambios.
7. Con la seña confirmada, llama a hacer_checkin con su id y la seña, y luego a recomendar con su id.
8. Cuéntale los matches de forma natural y en un par de frases cálidas: nombre, la razón concreta, hace cuánto llegó, y su seña para reconocerla.
9. Cierra la conversación deseándole un buen evento.

Reglas adicionales sobre nombres:
- Nunca digas en voz alta un nombre que la persona no haya confirmado.
- Si la transcripción de un turno posterior trae un nombre distinto al ya confirmado, ignóralo y sigue usando el nombre confirmado.'''

TOOLS = [
    {"type": "function", "name": "buscar_persona",
     "description": "Busca a una persona ya registrada al evento por nombre (y opcionalmente email, que si viene tiene prioridad) para confirmar quién llegó a la mesa. Tolera errores de transcripción del nombre; devuelve hasta 5 resultados, cada uno con \"confianza\" (\"alta\" o \"media\") según qué tan segura es la coincidencia.",
     "parameters": {"type": "object", "properties": {
         "nombre": {"type": "string", "description": "Nombre dicho por la persona"},
         "email": {"type": "string", "description": "Correo, si lo mencionó"}},
      "required": ["nombre"]}},
    {"type": "function", "name": "confirmar_perfil",
     "description": "Actualiza campos del perfil de la persona en este evento con lo que acaba de confirmar o corregir en la conversación.",
     "parameters": {"type": "object", "properties": {
         "id": {"type": "string", "description": "Id de la persona devuelto por buscar_persona"},
         "cambios": {"type": "object", "properties": {
             "busca": {"type": "string", "description": "Qué ayuda necesita"},
             "ofrece": {"type": "string", "description": "En qué puede ayudar a otros"},
             "problema": {"type": "string", "description": "Qué viene a resolver hoy"},
             "rol": {"type": "string", "description": "Su rol o profesión"}}}},
      "required": ["id", "cambios"]}},
    {"type": "function", "name": "hacer_checkin",
     "description": "Registra la llegada de la persona al evento con la seña con la que otros pueden reconocerla.",
     "parameters": {"type": "object", "properties": {
         "id": {"type": "string"},
         "sena": {"type": "string", "description": "Algo visible que lleve puesto o consigo, p. ej. color de camisa"}},
      "required": ["id", "sena"]}},
    {"type": "function", "name": "recomendar",
     "description": "Devuelve hasta dos personas ya presentes en el evento con quién le convendría hablar, y por qué.",
     "parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
    {"type": "function", "name": "mostrar_qr_registro",
     "description": "Muestra el QR/enlace para que la persona se registre al evento por su cuenta.",
     "parameters": {"type": "object", "properties": {}}},
]


def _prompt_transcripcion():
    """Pista de vocabulario para el transcriptor: nombres reales de asistentes registrados
    más algunos nombres/palabras comunes del evento, para que gpt-4o-mini-transcribe no
    confunda "Jacobo" con "Juan" o "Acu"."""
    nombres = []
    try:
        with connect() as db:
            rows = db.execute('SELECT profile FROM users WHERE demo=0').fetchall()
        for row in rows:
            try:
                data = json.loads(row['profile']) if row['profile'] else {}
            except (ValueError, TypeError):
                data = {}
            nombre = str((data or {}).get('name', '') or '').strip()
            if nombre:
                nombres.append(nombre)
            if len(nombres) >= 60:
                break
    except Exception:
        nombres = []
    extra = ['Jacobo', 'Juan', 'Laura', 'Andrés', 'Camila', 'Santiago', 'Valentina']
    prompt = ('Registro de evento en Medellín. Nombres de asistentes: '
              + ', '.join(nombres + extra)
              + '. Palabras: registré, registro, check-in, cofundador, backend, frontend, diseño, agentes.')
    return prompt[:800]


def crear_token_realtime():
    """POST a /v1/realtime/client_secrets (reemplaza al /v1/realtime/sessions deprecado)."""
    if not OPENAI_API_KEY:
        raise Problem('OPENAI_API_KEY no está configurada en el servidor. / OPENAI_API_KEY is not configured.', 500)
    turn_detection = None
    if os.getenv('REALTIME_VAD') == '1':
        turn_detection = {'type': 'server_vad', 'silence_duration_ms': 700}
    body = {
        'session': {
            'type': 'realtime',
            'model': os.getenv('REALTIME_MODEL', 'gpt-realtime'),
            'instructions': INSTRUCCIONES,
            # Sin server_vad, el navegador hace push-to-talk (input_audio_buffer.commit manual);
            # la mesa es ruidosa y esperar silencio natural dispararía respuestas de más.
            'audio': {
                'input': {
                    # verificar: que el campo se llame "prompt" (no "hints" ni similar) dentro de
                    # session.audio.input.transcription para el modelo gpt-4o-mini-transcribe.
                    'transcription': {'model': 'gpt-4o-mini-transcribe', 'language': 'es', 'prompt': _prompt_transcripcion()},
                    'turn_detection': turn_detection,
                },
                'output': {'voice': os.getenv('REALTIME_VOICE', 'marin')},
            },
            'tools': TOOLS,
            'tool_choice': 'auto',
        }
    }  # verificar: forma exacta del body de /v1/realtime/client_secrets (session.type, session.audio.*)
    req = urllib.request.Request('https://api.openai.com/v1/realtime/client_secrets', data=json.dumps(body).encode(), method='POST')
    req.add_header('Authorization', f'Bearer {OPENAI_API_KEY}')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors='replace')[:300]
        raise Problem(f'OpenAI Realtime rechazó la solicitud de token ({exc.code}): {detail} / OpenAI Realtime rejected the token request.', 502)
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise Problem('No se pudo contactar a OpenAI Realtime. / Could not reach OpenAI Realtime.', 502)
    # verificar: la respuesta documentada trae "value"/"expires_at" en la raíz; se acepta también
    # un anidamiento bajo "client_secret" por si la API cambia de forma.
    nested = data.get('client_secret') if isinstance(data.get('client_secret'), dict) else {}
    value = data.get('value') or nested.get('value')
    expires_at = data.get('expires_at') or nested.get('expires_at')
    if not value:
        raise Problem('Respuesta inesperada de OpenAI Realtime. / Unexpected OpenAI Realtime response.', 502)
    return {'value': value, 'expires_at': expires_at}


def _normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', str(text or '').lower()) if unicodedata.category(c) != 'Mn')


def _perfil_de(row):
    general = json.loads(row['profile']) if row['profile'] else {}
    evento = json.loads(row['data']) if row['data'] else {}
    return general, evento


def _ratio_parcial(a, b):
    """Similitud tolerante a diferencias de longitud (ej. "Jacou" por "Jacobo" mal
    transcrito): compara la cadena corta contra el ratio completo y contra cada ventana
    de la cadena larga del mismo tamaño, y toma la mejor — evita que un token registrado
    más largo diluya el ratio de un token dicho más corto."""
    corta, larga = (a, b) if len(a) <= len(b) else (b, a)
    mejor = difflib.SequenceMatcher(None, corta, larga).ratio()
    for i in range(len(larga) - len(corta) + 1):
        mejor = max(mejor, difflib.SequenceMatcher(None, corta, larga[i:i + len(corta)]).ratio())
    return mejor


def _mejor_ratio_tokens(tokens_buscados, tokens_nombre):
    """Mejor similitud entre cualquier par de tokens (nombre dicho vs. nombre registrado):
    ratio parcial de difflib.SequenceMatcher, o 0.8 si un token buscado (>=3 letras) es
    prefijo de uno registrado (cubre "deletreó/dijo solo el primer nombre")."""
    mejor = 0.0
    for qt in tokens_buscados:
        for nt in tokens_nombre:
            if qt == nt:
                return 1.0
            r = _ratio_parcial(qt, nt)
            if len(qt) >= 3 and nt.startswith(qt):
                r = max(r, 0.8)
            mejor = max(mejor, r)
    return mejor


def buscar_persona(nombre='', email='', event=EVENT):
    nombre = str(nombre or '').strip()
    email = str(email or '').strip().lower()
    if not nombre and not email:
        raise Problem('Falta el nombre para buscar. / Missing name to search.')
    with connect() as db:
        rows = db.execute('''SELECT u.id,u.email,u.profile,p.data FROM users u
          LEFT JOIN profiles p ON p.user_id=u.id AND p.event_id=? WHERE u.demo=0''', (event,)).fetchall()
    query = _normalized(nombre)
    tokens = [t for t in query.split(' ') if t]
    resultados = []
    for row in rows:
        general, evento = _perfil_de(row)
        name = general.get('name', '')
        name_norm = _normalized(name)
        name_tokens = [t for t in name_norm.split(' ') if t]
        is_email_match = bool(email) and row['email'].lower() == email
        # LIKE normalizado (sin tildes) original: substring completo o todos los tokens presentes.
        is_substr_match = bool(query) and (query in name_norm or (tokens and all(t in name_norm for t in tokens)))
        # Tolerante a errores de transcripción: similitud difusa token a token.
        ratio = _mejor_ratio_tokens(tokens, name_tokens) if (tokens and name_tokens) else 0.0
        if not (is_email_match or is_substr_match or ratio >= 0.75):
            continue
        score = ratio
        if is_substr_match:
            score = max(score, 0.95)
        if is_email_match:
            score = 1.0
        confianza = 'alta' if (is_email_match or score >= 0.9) else 'media'
        resultados.append({
            'id': row['id'], 'name': name, 'role': general.get('role', ''), 'sector': general.get('sector', ''),
            'busca': ' · '.join(x for x in (evento.get('help', ''), evento.get('problem', '')) if x),
            'ofrece': evento.get('skills', ''),
            'registrado': row['data'] is not None,
            'confianza': confianza,
            '_score': score,
        })
        if is_email_match:
            resultados[-1].pop('_score')
            return [resultados[-1]]
    resultados.sort(key=lambda r: -r['_score'])
    for r in resultados:
        r.pop('_score')
    return resultados[:5]


CAMPOS_CAMBIO = {'busca': ('event', 'help'), 'problema': ('event', 'problem'), 'ofrece': ('event', 'skills'), 'rol': ('general', 'role')}


def confirmar_perfil(id, cambios, event=EVENT):
    if not isinstance(cambios, dict) or not cambios:
        raise Problem('No hay cambios que confirmar. / No changes to confirm.')
    with connect() as db:
        row = db.execute('''SELECT u.id,u.email,u.profile,p.data FROM users u
          LEFT JOIN profiles p ON p.user_id=u.id AND p.event_id=? WHERE u.id=?''', (event, id)).fetchone()
        if not row:
            raise Problem('Persona no encontrada. / Person not found.', 404)
        general, evento = _perfil_de(row)
        for clave, valor in cambios.items():
            destino = CAMPOS_CAMBIO.get(clave)
            if not destino or not isinstance(valor, str) or not valor.strip():
                continue
            valor = valor.strip()[:1500]
            (general if destino[0] == 'general' else evento)[destino[1]] = valor
        db.execute('UPDATE users SET profile=? WHERE id=?', (json.dumps(general), id))
        db.execute('''INSERT INTO profiles(user_id,event_id,data,visible) VALUES (?,?,?,1)
          ON CONFLICT(user_id,event_id) DO UPDATE SET data=excluded.data''', (id, event, json.dumps(evento)))
    return {'confirmado': True, 'rol': general.get('role', ''), 'busca': evento.get('help', ''), 'problema': evento.get('problem', ''), 'ofrece': evento.get('skills', '')}


def hacer_checkin(id, sena, event=EVENT):
    sena = str(sena or '').strip()[:200]
    if not sena:
        raise Problem('Falta la seña para reconocer a la persona. / Missing distinguishing mark.')
    with connect() as db:
        row = db.execute('''SELECT u.id,u.email,u.profile,p.data FROM users u
          LEFT JOIN profiles p ON p.user_id=u.id AND p.event_id=? WHERE u.id=?''', (event, id)).fetchone()
        if not row:
            raise Problem('Persona no encontrada. / Person not found.', 404)
        checked_in_at = time.time()
        db.execute('''INSERT INTO checkins(user_id,event_id,checked_in_at,sena) VALUES (?,?,?,?)
          ON CONFLICT(user_id) DO UPDATE SET event_id=excluded.event_id,checked_in_at=excluded.checked_in_at,sena=excluded.sena''',
                   (id, event, checked_in_at, sena))
        general, evento = _perfil_de(row)
    perfil = {**general, **evento, 'id': id, 'email': row['email'], 'sena': sena, 'checked_in_at': checked_in_at}
    ambiguous.registrar_asistente(perfil, event)
    ambiguous.avisar_staff(f"Llegó {general.get('name', 'alguien')} ({general.get('role', 'sin rol')}). Anda de {sena}.")
    return {'checked_in': True, 'checked_in_at': checked_in_at, 'sena': sena}


NEED_FIELDS = ('help', 'problem')
OFFER_FIELDS = ('skills', 'knowledge', 'services')
AFFINITY_FIELDS = ('sector', 'interests')


def _joined(perfil, campos):
    return ' '.join(perfil.get(c, '') for c in campos if perfil.get(c))


def recomendar(id, event=EVENT):
    with connect() as db:
        own_row = db.execute('''SELECT u.id,u.profile,p.data FROM users u
          LEFT JOIN profiles p ON p.user_id=u.id AND p.event_id=? WHERE u.id=?''', (event, id)).fetchone()
        if not own_row:
            raise Problem('Persona no encontrada. / Person not found.', 404)
        checkin_rows = db.execute('''SELECT u.id,u.profile,p.data,c.checked_in_at,c.sena FROM checkins c
          JOIN users u ON u.id=c.user_id LEFT JOIN profiles p ON p.user_id=u.id AND p.event_id=c.event_id
          WHERE c.event_id=? AND c.user_id!=?''', (event, id)).fetchall()
        todos_rows = db.execute('SELECT u.profile,p.data FROM users u JOIN profiles p ON p.user_id=u.id WHERE p.event_id=?', (event,)).fetchall()

    own_general, own_evento = _perfil_de(own_row)
    own = {**own_general, **own_evento}
    own_need, own_offer, own_affinity = terms(_joined(own, NEED_FIELDS)), terms(_joined(own, OFFER_FIELDS)), terms(_joined(own, AFFINITY_FIELDS))

    candidatos = []
    for row in checkin_rows:
        general, evento = _perfil_de(row)
        perfil = {**general, **evento}
        need, offer, affinity = terms(_joined(perfil, NEED_FIELDS)), terms(_joined(perfil, OFFER_FIELDS)), terms(_joined(perfil, AFFINITY_FIELDS))
        te_ayuda, ayudas = sorted(own_need & offer), sorted(own_offer & need)
        necesidad_comun, interes_comun = sorted(own_need & need), sorted(own_affinity & affinity)
        score = 3 * len(te_ayuda) + 3 * len(ayudas) + 2 * len(necesidad_comun) + len(interes_comun) + (3 if te_ayuda and ayudas else 0)
        if score <= 0:
            continue
        nombre = general.get('name', '')
        if te_ayuda:
            razon = f"{nombre} puede ayudarte con {', '.join(te_ayuda)}."
        elif ayudas:
            razon = f"Tú puedes ayudar a {nombre} con {', '.join(ayudas)}."
        elif necesidad_comun:
            razon = f"Ambos buscan lo mismo: {', '.join(necesidad_comun)}."
        else:
            razon = f"Comparten interés en {', '.join(interes_comun)}."
        candidatos.append({'id': row['id'], 'name': nombre, 'role': general.get('role', ''), 'razon': razon,
                            'minutos_desde_llegada': max(0, int((time.time() - row['checked_in_at']) / 60)),
                            'sena': row['sena'], '_score': score})

    candidatos.sort(key=lambda c: (-c['_score'], c['name']))
    top = candidatos[:2]
    for c in top:
        c.pop('_score')

    if not top:
        necesita, ofrece = {}, {}
        for row in todos_rows:
            general, evento = _perfil_de(row)
            perfil = {**general, **evento}
            for tag in terms(_joined(perfil, NEED_FIELDS)):
                necesita[tag] = necesita.get(tag, 0) + 1
            for tag in terms(_joined(perfil, OFFER_FIELDS)):
                ofrece[tag] = ofrece.get(tag, 0) + 1
        vacios = sorted(tag for tag, n in necesita.items() if n >= 3 and ofrece.get(tag, 0) == 0)
        if vacios:
            ambiguous.crear_tarea(
                f"Nadie en el evento ofrece: {', '.join(vacios)}",
                f"{len(vacios)} tema(s) que 3 o más personas buscan y nadie ofrece todavía en {event}.", 'medium')
        sugerencia = ('Todavía no ha llegado nadie que combine bien contigo; en un rato vuelvo a intentarlo.'
                      if not checkin_rows else 'Ya llegaron algunas personas, pero ninguna combina claramente contigo todavía.')
        return {'recomendaciones': [], 'sugerencia': sugerencia}

    for c in top:
        ambiguous.registrar_conexion({'name': own.get('name', '')}, {'name': c['name']}, c['razon'], event)
    return {'recomendaciones': top}


def _ip_lan():
    """IP en la red local de esta máquina (truco del UDP connect a 8.8.8.8: no envía
    tráfico real, solo hace que el SO elija la interfaz de salida). Si falla (sin red),
    cae a loopback."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return '127.0.0.1'


def mostrar_qr_registro():
    # El kiosco no usa Next.js, pero se admite el nombre pedido por convención de otros
    # proyectos del equipo; REGISTER_URL es la variable "propia" de este backend.
    url = os.getenv('REGISTER_URL') or os.getenv('NEXT_PUBLIC_REGISTER_URL')
    if not url:
        port = os.getenv('PORT', '8000')
        url = f'http://{_ip_lan()}:{port}/'
    return {'url': url, 'nota': 'escanea desde tu celular'}
