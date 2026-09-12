import json
import time
import uuid
from backend.db import connect
from backend.modules.auth import Problem
from backend.modules.notifications import notify
from backend.modules.matching import public_profile

def blocked(db, a, b):
    return db.execute('SELECT 1 FROM blocks WHERE (user_id=? AND target=?) OR (user_id=? AND target=?)', (a,b,b,a)).fetchone()

def invite(user, event, target):
    with connect() as db:
        own = db.execute('SELECT data FROM profiles WHERE user_id=? AND event_id=?', (user['id'],event)).fetchone()
        other = db.execute('SELECT p.*,u.demo FROM profiles p JOIN users u ON u.id=p.user_id WHERE p.user_id=? AND p.event_id=?', (target,event)).fetchone()
        if target == user['id'] or not own or not other or not other['visible'] or blocked(db,user['id'],target):
            raise Problem('Participante no disponible. / Participant unavailable.', 404)
        if other['demo']:
            raise Problem('Perfil ficticio de demostración. Usa dos cuentas reales para probar invitaciones. / Demo profile: use two real accounts to test invitations.')
        if json.loads(other['data']).get('availability') == 'unavailable' or json.loads(own['data']).get('availability') == 'unavailable':
            raise Problem('Participante sin disponibilidad. / Participant unavailable.', 409)
        prior = db.execute('SELECT * FROM invitations WHERE event_id=? AND ((sender=? AND recipient=?) OR (sender=? AND recipient=?))', (event,user['id'],target,target,user['id'])).fetchone()
        if prior:
            raise Problem('Ya existe una invitación entre estos participantes. Revisa Conexiones. / An invitation already exists. Check Connections.',409)
        iid = uuid.uuid4().hex
        db.execute('INSERT INTO invitations VALUES (?,?,?,?,?,?)', (iid,event,user['id'],target,'pending',time.time()))
        notify(db,target,'invitation_received')
    return {'id': iid, 'status': 'pending'}

def respond(user, iid, action):
    if action not in ('accepted','rejected'):
        raise Problem('Respuesta inválida. / Invalid response.')
    with connect() as db:
        row = db.execute('SELECT * FROM invitations WHERE id=? AND recipient=?', (iid,user['id'])).fetchone()
        if not row or blocked(db, row['sender'],user['id']):
            raise Problem('Invitación no encontrada. / Invitation not found.',404)
        if row['status'] != 'pending':
            raise Problem('La invitación ya fue respondida. / Invitation already answered.',409)
        db.execute('UPDATE invitations SET status=? WHERE id=?', (action,iid))
        notify(db,row['sender'],'invitation_' + action)
    return {'status': action}

def connections(user,event):
    result = []
    with connect() as db:
        rows = db.execute('SELECT * FROM invitations WHERE event_id=? AND (sender=? OR recipient=?) ORDER BY created DESC', (event,user['id'],user['id'])).fetchall()
        for row in rows:
            target = row['recipient'] if row['sender'] == user['id'] else row['sender']
            if blocked(db,user['id'],target):
                continue
            person = db.execute('SELECT u.id,u.profile,u.demo,p.data FROM users u JOIN profiles p ON p.user_id=u.id WHERE u.id=? AND p.event_id=?', (target,event)).fetchone()
            if not person:
                continue
            p = public_profile(person)
            data = json.loads(person['data'])
            # Each participant controls disclosure of their own contact, independently.
            if row['status'] == 'accepted' and data.get('share_contact') is True:
                p['contact'] = data.get('contact', '')
            result.append({**dict(row), 'incoming': row['recipient'] == user['id'], 'person': p})
    return result

def block(user,target):
    with connect() as db:
        if target == user['id'] or not db.execute('SELECT id FROM users WHERE id=?', (target,)).fetchone():
            raise Problem('Participante inválido. / Invalid participant.')
        db.execute('INSERT OR IGNORE INTO blocks VALUES (?,?)', (user['id'],target))
    return {'blocked': True}
