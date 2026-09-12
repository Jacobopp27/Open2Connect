import json
from backend.db import connect
from backend.modules.auth import Problem

GENERAL = ['name', 'role', 'experience', 'sector', 'interests', 'languages']
EVENT = ['purpose', 'problem', 'help', 'priority', 'outcome', 'skills', 'knowledge', 'services', 'resources', 'availability', 'contact']
REQUIRED = ['name', 'role', 'languages', 'purpose', 'problem', 'help', 'priority', 'outcome', 'skills', 'availability']

def check_event(db, event):
    if not db.execute('SELECT id FROM events WHERE id=?', (event,)).fetchone():
        raise Problem('Evento no encontrado. / Event not found.', 404)

def get_profile(user, event):
    with connect() as db:
        check_event(db, event)
        row = db.execute('SELECT data,visible FROM profiles WHERE user_id=? AND event_id=?', (user['id'], event)).fetchone()
    return {**json.loads(user['profile']), **(json.loads(row['data']) if row else {}), 'visible': bool(row['visible']) if row else True, 'saved': bool(row)}

def clean(data):
    if not isinstance(data, dict):
        raise Problem('Perfil inválido. / Invalid profile.')
    result = {}
    for key in GENERAL + EVENT:
        val = data.get(key, '')
        if not isinstance(val, str) or len(val) > 1500:
            raise Problem('Campo inválido o demasiado largo. / Invalid or overly long field.')
        result[key] = val.strip()
    result['share_contact'] = data.get('share_contact') is True
    result['visible'] = data.get('visible', True) is True
    return result

def save_profile(user, event, payload):
    if payload.get('confirmed') is not True:
        raise Problem('Confirma el resumen antes de guardar. / Confirm the summary before saving.')
    data = clean(payload.get('profile', {}))
    missing = [key for key in REQUIRED if not data[key]]
    if missing:
        raise Problem('Completa los campos obligatorios: / Complete required fields: ' + ', '.join(missing))
    if data['priority'] not in ('high', 'medium', 'low') or data['availability'] not in ('available', 'limited', 'unavailable'):
        raise Problem('Selecciona prioridad y disponibilidad válidas. / Select valid priority and availability.')
    with connect() as db:
        check_event(db, event)
        db.execute('UPDATE users SET profile=? WHERE id=?', (json.dumps({key: data[key] for key in GENERAL}), user['id']))
        event_data = {key: data[key] for key in EVENT + ['share_contact']}
        db.execute('INSERT INTO profiles VALUES (?,?,?,?) ON CONFLICT(user_id,event_id) DO UPDATE SET data=excluded.data,visible=excluded.visible', (user['id'], event, json.dumps(event_data), int(data['visible'])))
    return {'saved': True}
