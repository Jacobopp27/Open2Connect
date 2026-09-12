"""Página personal del asistente ("/yo/<id>"): sus matches en vivo y confirmación
de "ya nos conocimos".

`estado()` se llama cada 10s desde el celular del asistente (ver frontend/yo.js), así
que NO puede reusar kiosk.recomendar() tal cual: esa función escribe una fila de
"conexión sugerida" en la hoja de Ambiguous cada vez que corre, y llamarla en cada
poll inundaría la hoja de filas duplicadas. En su lugar, este módulo duplica la
lógica de puntaje de kiosk.recomendar en una función de solo lectura (sin
kiosk.registrar_conexion ni escrituras de ningún tipo), pero calculando contra
TODOS los perfiles del evento (no solo los que ya hicieron check-in) y enriqueciendo
cada candidato con su checked_in_at (o None si aún no ha llegado) — así el frontend
puede detectar el momento en que un match pasa de "no ha llegado" a "llegó".

Tabla nueva `encuentros`: confirmación explícita ("ya nos conocimos") hecha por
cualquiera de los dos asistentes desde su página personal.
"""
import json
import logging
import threading
import time
from backend.db import connect
from backend.modules import ambiguous
from backend.modules.kiosk import EVENT, NEED_FIELDS, OFFER_FIELDS, AFFINITY_FIELDS, _joined, _perfil_de
from backend.modules.matching import terms

with connect() as _db:
    _db.execute('''CREATE TABLE IF NOT EXISTS encuentros (
      user_a TEXT NOT NULL, user_b TEXT NOT NULL, event_id TEXT NOT NULL, confirmado_en REAL NOT NULL,
      PRIMARY KEY(user_a,user_b,event_id))''')


def _par(a, b):
    """Ordena el par para que (a,b) y (b,a) sean siempre la misma fila."""
    return (a, b) if a <= b else (b, a)


def _matches_de(id, event):
    """Copia de solo lectura del puntaje de kiosk.recomendar, contra todos los perfiles
    del evento (no solo quienes ya hicieron check-in). Devuelve None si `id` no existe."""
    with connect() as db:
        own_row = db.execute('''SELECT u.id,u.profile,p.data FROM users u
          LEFT JOIN profiles p ON p.user_id=u.id AND p.event_id=? WHERE u.id=?''', (event, id)).fetchone()
        if not own_row:
            return None
        rows = db.execute('''SELECT u.id,u.profile,p.data,c.checked_in_at,c.sena FROM users u
          JOIN profiles p ON p.user_id=u.id AND p.event_id=?
          LEFT JOIN checkins c ON c.user_id=u.id AND c.event_id=?
          WHERE u.id!=? AND u.demo=0''', (event, event, id)).fetchall()

    own_general, own_evento = _perfil_de(own_row)
    own = {**own_general, **own_evento}
    own_need = terms(_joined(own, NEED_FIELDS))
    own_offer = terms(_joined(own, OFFER_FIELDS))
    own_affinity = terms(_joined(own, AFFINITY_FIELDS))

    candidatos = []
    for row in rows:
        general, evento = _perfil_de(row)
        perfil = {**general, **evento}
        need = terms(_joined(perfil, NEED_FIELDS))
        offer = terms(_joined(perfil, OFFER_FIELDS))
        affinity = terms(_joined(perfil, AFFINITY_FIELDS))
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
        candidatos.append({
            'id': row['id'], 'name': nombre, 'role': general.get('role', ''), 'razon': razon,
            'sena': row['sena'] or '', 'checked_in_at': row['checked_in_at'], '_score': score,
        })

    candidatos.sort(key=lambda c: (-c['_score'], c['name']))
    for c in candidatos:
        c.pop('_score')
    return own_general, candidatos


def estado(user_id, event=EVENT):
    user_id = str(user_id or '')
    resultado = _matches_de(user_id, event) if user_id else None
    if resultado is None:
        return {'error': 'no encontrado'}
    own_general, candidatos = resultado

    with connect() as db:
        filas = db.execute('SELECT user_a,user_b FROM encuentros WHERE event_id=? AND (user_a=? OR user_b=?)',
                            (event, user_id, user_id)).fetchall()
    conocidos_ids = {(f['user_b'] if f['user_a'] == user_id else f['user_a']) for f in filas}

    matches = []
    for c in candidatos:
        checked_in_at = c['checked_in_at']
        minutos = max(0, int((time.time() - checked_in_at) / 60)) if checked_in_at else None
        matches.append({
            'id': c['id'], 'name': c['name'], 'role': c['role'], 'razon': c['razon'], 'sena': c['sena'],
            'checked_in_at': checked_in_at, 'minutos_desde_llegada': minutos,
            'conocidos': c['id'] in conocidos_ids,
        })

    return {'yo': {'id': user_id, 'name': own_general.get('name', '')}, 'matches': matches, 'actualizado': time.time()}


def _marcar_conocidos_en_hoja(nombre_a, nombre_b, event):
    """Busca en la hoja de conexiones la fila 'sugerida' entre estas dos personas y la
    marca 'se conocieron'. Best-effort: nunca lanza, y en modo local solo hace logging.
    # verificar: forma exacta de cada fila que devuelve _filas_actuales (se toleran tanto
    # listas posicionales [A,B,C,D,E,F] como dicts {"A":..,"B":..,...})."""
    if not ambiguous.AGENT_KEY or not ambiguous.SHEET_ID:
        logging.info('[encuentros:local] %s y %s se conocieron (%s)', nombre_a, nombre_b, event)
        return
    try:
        filas = ambiguous._filas_actuales(ambiguous.SHEET_ID)
        for i, fila in enumerate(filas):
            if isinstance(fila, dict):
                c_val, d_val, f_val = fila.get('C', ''), fila.get('D', ''), fila.get('F', '')
            else:
                valores = list(fila) if isinstance(fila, (list, tuple)) else []
                c_val = valores[2] if len(valores) > 2 else ''
                d_val = valores[3] if len(valores) > 3 else ''
                f_val = valores[5] if len(valores) > 5 else ''
            nombres_fila = {str(c_val), str(d_val)}
            if nombre_a in nombres_fila and nombre_b in nombres_fila and str(f_val).strip().lower() == 'sugerida':
                ambiguous._request('PATCH', f'sheets/{ambiguous.SHEET_ID}/cells', {'updates': [{'row': i, 'column': 'F', 'value': 'se conocieron'}]})
                break
    except Exception:
        logging.exception('[encuentros] no se pudo marcar la fila de conexión como conocidos')


def confirmar(user_id, otro_id, event=EVENT):
    user_id, otro_id = str(user_id or ''), str(otro_id or '')
    if not user_id or not otro_id or user_id == otro_id:
        return {'error': 'faltan ids'}
    a, b = _par(user_id, otro_id)
    with connect() as db:
        rows = db.execute('SELECT id,profile FROM users WHERE id IN (?,?)', (a, b)).fetchall()
        if len(rows) != 2:
            return {'error': 'no encontrado'}
        nombres = {r['id']: (json.loads(r['profile']) if r['profile'] else {}).get('name', '') for r in rows}
        db.execute('INSERT OR IGNORE INTO encuentros(user_a,user_b,event_id,confirmado_en) VALUES (?,?,?,?)',
                   (a, b, event, time.time()))

    nombre_a, nombre_b = nombres.get(a, ''), nombres.get(b, '')
    threading.Thread(target=_marcar_conocidos_en_hoja, args=(nombre_a, nombre_b, event), daemon=True).start()
    ambiguous.avisar_staff(f"{nombre_a} y {nombre_b} se conocieron.")
    return {'ok': True}


def handle(path, post, payload, query, event):
    """Rutas de /yo: sin sesión de usuario — el id del asistente viaja en su QR
    personal (token de 32 hex), igual que las rutas de kiosco no exigen sesión."""
    if path == '/api/yo/estado' and not post:
        return estado(str(query.get('id', [''])[0]), event)
    if path == '/api/yo/confirmar' and post:
        return confirmar(str(payload.get('id', '')), str(payload.get('otro', '')), event)
    return None
