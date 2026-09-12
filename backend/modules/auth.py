import hashlib
import hmac
import secrets
import time
import uuid
from backend.db import connect

class Problem(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return salt + ':' + digest

def authenticate(payload, register=False):
    email = str(payload.get('email', '')).strip().lower()
    password = str(payload.get('password', ''))
    if '@' not in email or len(email) > 254 or not 10 <= len(password) <= 128:
        raise Problem('Usa un correo válido y contraseña de 10 a 128 caracteres. / Use a valid email and a 10–128 character password.')
    with connect() as db:
        if register:
            if db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
                raise Problem('Ese correo ya está registrado. / Email already registered.', 409)
            uid = uuid.uuid4().hex
            db.execute('INSERT INTO users(id,email,password) VALUES (?,?,?)', (uid, email, password_hash(password)))
        else:
            row = db.execute('SELECT * FROM users WHERE email=? AND demo=0', (email,)).fetchone()
            expected = row['password'] if row else password_hash('dummy-password')
            if not hmac.compare_digest(password_hash(password, expected.split(':')[0]), expected) or not row:
                raise Problem('Credenciales incorrectas. / Invalid credentials.', 401)
            uid = row['id']
        token = secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
        db.execute('INSERT INTO sessions VALUES (?,?,?)', (token, uid, time.time() + 86400 * 7))
    return token

def current_user(token):
    with connect() as db:
        row = db.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?', (token, time.time())).fetchone()
    if not row:
        raise Problem('Inicia sesión para continuar. / Sign in to continue.', 401)
    return dict(row)
