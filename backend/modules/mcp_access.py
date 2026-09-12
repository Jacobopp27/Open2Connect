"""Short-lived, event-scoped app tokens for the local MCP bridge."""
import hashlib
import secrets
import time
from backend.db import connect
from backend.modules.auth import Problem
from backend.modules.profiles import check_event

ALLOWED={'/api/interviews/start','/api/interviews/turn','/api/interviews/summary','/api/interviews/confirm','/api/interviews/control','/api/interviews/draft','/api/profile'}

def mint(user,event,session):
    token=secrets.token_urlsafe(32);expires=time.time()+3600
    with connect() as db:
        check_event(db,event)
        db.execute('INSERT INTO mcp_tokens VALUES (?,?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],event,expires,session))
    return {'token':token,'expires':expires,'event':event,'scope':'own_profile_interview'}

def authenticate(token,path,post):
    if path not in ALLOWED or (path=='/api/profile' and post):raise Problem('Fuera del alcance MCP. / Outside MCP scope.',403)
    digest=hashlib.sha256(token.encode()).hexdigest()
    with connect() as db:
        row=db.execute('SELECT u.*,m.event_id FROM mcp_tokens m JOIN users u ON u.id=m.user_id JOIN sessions s ON s.token=m.session_token WHERE m.hash=? AND m.expires>? AND s.expires>?',(digest,time.time(),time.time())).fetchone()
    if not row:raise Problem('Token MCP inválido o vencido. / Invalid or expired MCP token.',401)
    user=dict(row);user['mcp_event']=user.pop('event_id')
    return user

def revoke(user):
    with connect() as db:db.execute('DELETE FROM mcp_tokens WHERE user_id=?',(user['id'],))
    return {'revoked':True}
