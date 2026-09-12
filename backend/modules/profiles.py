import json
from backend.db import connect
from backend.modules.auth import Problem

GENERAL = ['name', 'role', 'experience', 'sector', 'interests', 'languages']
EVENT = ['needs_status', 'offers_status', 'purpose', 'problem', 'help', 'priority', 'outcome', 'skills', 'knowledge', 'services', 'resources', 'availability', 'contact']
REQUIRED = ['name', 'role', 'languages', 'purpose', 'problem', 'help', 'priority', 'outcome', 'skills', 'availability']

def check_event(db, event):
    if not db.execute('SELECT id FROM events WHERE id=?', (event,)).fetchone():
        raise Problem('Evento no encontrado. / Event not found.', 404)

def get_profile(user, event):
    from backend.adapters.profile_store import store
    with connect() as db:
        check_event(db, event)
    return store().get(user['id'], event)


def clean(data):
    if not isinstance(data, dict):
        raise Problem('Perfil inválido. / Invalid profile.')
    result = {}
    for key in GENERAL + EVENT:
        val = data.get(key, '')
        if not isinstance(val, str) or len(val) > 1500:
            raise Problem('Campo inválido o demasiado largo. / Invalid or overly long field.')
        result[key] = val.strip()
    for key in ('needs_status', 'offers_status'):
        result[key] = result[key] or 'present'
        if result[key] not in ('present', 'none'):
            raise Problem('Estado de necesidad/oferta inválido. / Invalid needs/offers status.')
    result['share_contact'] = data.get('share_contact') is True
    result['visible'] = data.get('visible', True) is True
    return result

def missing_fields(data):
    required = ['name', 'role', 'languages', 'purpose', 'availability']
    if data.get('needs_status') != 'none':
        required += ['problem', 'help', 'priority', 'outcome']
    if data.get('offers_status') != 'none':
        required += ['skills']
    return [key for key in required if not data.get(key)]

def validate_profile(data):
    data = clean(data)
    missing = missing_fields(data)
    if missing:
        raise Problem('Completa los campos obligatorios: / Complete required fields: ' + ', '.join(missing))
    if data['needs_status'] == 'none':
        for key in ('problem', 'help', 'priority', 'outcome'):
            data[key] = ''
    if data['offers_status'] == 'none':
        for key in ('skills', 'knowledge', 'services', 'resources'):
            data[key] = ''
    if (data['needs_status'] != 'none' and data['priority'] not in ('high', 'medium', 'low')) or data['availability'] not in ('available', 'limited', 'unavailable'):
        raise Problem('Selecciona prioridad y disponibilidad válidas. / Select valid priority and availability.')
    return data

def save_profile(user, event, payload):
    if payload.get('confirmed') is not True:
        raise Problem('Confirma el resumen antes de guardar. / Confirm the summary before saving.')
    data = validate_profile(payload.get('profile', {}))
    with connect() as db:
        check_event(db, event)
    from backend.adapters.profile_store import store
    store().save(user['id'], event, {key: data[key] for key in GENERAL}, {key: data[key] for key in EVENT + ['share_contact']}, data['visible'])
    return {'saved': True}
