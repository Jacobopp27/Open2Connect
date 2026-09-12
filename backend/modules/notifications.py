import time
import uuid
from backend.db import connect

def notify(db, user_id, code):
    db.execute('INSERT INTO notifications VALUES (?,?,?,?)', (uuid.uuid4().hex, user_id, code, time.time()))

def list_notifications(user):
    with connect() as db:
        return [dict(row) for row in db.execute('SELECT id,message,created FROM notifications WHERE user_id=? ORDER BY created DESC LIMIT 20', (user['id'],))]
