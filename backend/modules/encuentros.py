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
import os
import logging
import threading
import time
from backend.db import connect
from backend.modules import ambiguous
from backend.modules.kiosk import EVENT, NEED_FIELDS, OFFER_FIELDS, AFFINITY_FIELDS, _joined, _perfil_de
from backend.modules.matching import terms

def _par(a, b):
    """Ordena el par para que (a,b) y (b,a) sean siempre la misma fila."""
    return (a, b) if a <= b else (b, a)


def _matches_de(id, event):
    from backend.modules.matching import recommendations
    from backend.adapters.profile_store import store
    from backend.modules.auth import Problem
    own = store().get(id,event)
    if not own.get('saved'): return None
    matches = recommendations({'id':id},event)['recommendations']
    with connect() as db:
        arrivals={r['user_id']:dict(r) for r in db.execute('SELECT user_id,checked_in_at,sena FROM checkins WHERE event_id=?',(event,))}
    candidates=[]
    labels={'they_help':'Puede ayudarte con','you_help':'Puedes ayudarle con','shared_need':'Ambos buscan','affinity':'Comparten interés en'}
    for match in matches:
        person=match['person']
        if person.get('demo'): continue
        reason=match['reasons'][0]
        arrival=arrivals.get(person['id'],{})
        candidates.append({'id':person['id'],'name':person.get('name',''),'role':person.get('role',''),
            'razon':labels[reason['kind']] + ' ' + ', '.join(reason['terms']) + '.',
            'checked_in_at':arrival.get('checked_in_at'),'sena':arrival.get('sena','')})
    return own,candidates


def estado(user_id, event=EVENT):
    user_id = str(user_id or '')
    resultado = _matches_de(user_id, event) if user_id else None
    if resultado is None:
        from backend.modules.auth import Problem
        raise Problem('Completa y confirma tu perfil primero.',404)
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
    from backend.modules.auth import Problem
    if otro_id not in {c['id'] for c in estado(user_id,event)['matches']}:
        raise Problem('Participante no disponible en tus coincidencias.',404)
    a, b = _par(user_id, otro_id)
    with connect() as db:
        rows = db.execute('SELECT id,profile FROM users WHERE id IN (?,?)', (a, b)).fetchall()
        if len(rows) != 2:
            raise Problem('Participante no disponible.',404)
        nombres = {r['id']: (json.loads(r['profile']) if r['profile'] else {}).get('name', '') for r in rows}
        inserted = db.execute('INSERT OR IGNORE INTO encuentros(user_a,user_b,event_id,confirmado_en) VALUES (?,?,?,?)',
                   (a, b, event, time.time()))

    if not inserted.rowcount: return {'ok':True}
    nombre_a, nombre_b = nombres.get(a, ''), nombres.get(b, '')
    if os.getenv('ENABLE_EXTERNAL_SYNC') != '1': return {'ok':True}
    threading.Thread(target=_marcar_conocidos_en_hoja, args=(nombre_a, nombre_b, event), daemon=True).start()
    ambiguous.avisar_staff(f"{nombre_a} y {nombre_b} se conocieron.")
    return {'ok': True}
