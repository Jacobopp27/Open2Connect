"""Single selected source of truth for confirmed profiles; no implicit DB migration.

App authentication/events/connections remain local. Supabase's service key is
backend-only; application authorization, not RLS, scopes service-role operations.
"""
import json
import os
from backend.db import connect
from backend.modules.auth import Problem

class SQLiteProfiles:
    name = 'sqlite'
    def get(self, user_id, event):
        with connect() as db:
            user = db.execute('SELECT profile FROM users WHERE id=?', (user_id,)).fetchone()
            row = db.execute('SELECT data,visible FROM profiles WHERE user_id=? AND event_id=?', (user_id,event)).fetchone()
        return {**(json.loads(user['profile']) if user else {}), **(json.loads(row['data']) if row else {}), 'visible': bool(row['visible']) if row else True, 'saved': bool(row)}
    def save(self, user_id, event, general, data, visible):
        with connect() as db:
            db.execute('UPDATE users SET profile=? WHERE id=?', (json.dumps(general),user_id))
            db.execute('INSERT INTO profiles VALUES (?,?,?,?) ON CONFLICT(user_id,event_id) DO UPDATE SET data=excluded.data,visible=excluded.visible', (user_id,event,json.dumps(data),int(visible)))
    def participants(self, event):
        with connect() as db:
            return [dict(r) for r in db.execute('SELECT u.id,u.profile,u.demo,p.data,p.visible FROM users u JOIN profiles p ON p.user_id=u.id WHERE p.event_id=?',(event,))]

class SupabaseProfiles:
    name = 'supabase'
    def __init__(self, client=None):
        if client is not None:
            self.client = client
            return
        from urllib.parse import urlparse
        url = os.getenv('SUPABASE_URL','')
        key = os.getenv('SUPABASE_SECRET_KEY') or os.getenv('SUPABASE_SERVICE_ROLE_KEY','')
        parsed = urlparse(url)
        if not key or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise Problem('Supabase requiere URL HTTPS y clave de servidor. / Supabase requires HTTPS URL and server key.',503)
        try:
            from supabase import create_client
            from supabase.client import ClientOptions
        except ImportError:
            raise Problem('Instala requirements-integrations.txt. / Install requirements-integrations.txt.',503)
        self.client = create_client(url,key,options=ClientOptions(postgrest_client_timeout=10,auto_refresh_token=False,persist_session=False))
    def execute(self, query):
        try:
            return query.execute().data
        except Exception:
            # Never echo SDK errors: they may include URL, keys or private payloads.
            raise Problem('Supabase no disponible. Verifica conexión y migración; no se cambió a SQLite. / Supabase unavailable. Check connection and migration; no fallback write occurred.',503) from None
    def get(self, user_id, event):
        general = self.execute(self.client.table('o2c_general_profiles').select('data').eq('owner_id',user_id).limit(1))
        rows = self.execute(self.client.table('o2c_event_profiles').select('data,visible').eq('owner_id',user_id).eq('event_id',event).limit(1))
        row = rows[0] if rows else None
        return {**(general[0]['data'] if general else {}), **(row['data'] if row else {}), 'visible': row['visible'] if row else True, 'saved': bool(row)}
    def save(self, user_id, event, general, data, visible):
        self.execute(self.client.rpc('o2c_save_profile', {'p_owner':user_id,'p_event':event,'p_general':general,'p_data':data,'p_visible':visible}))
    def participants(self, event):
        rows=[]; offset=0
        while True:
            batch=self.execute(self.client.table('o2c_event_profiles').select('owner_id,data,visible,o2c_general_profiles(data)').eq('event_id',event).order('owner_id').range(offset,offset+499))
            rows.extend(batch)
            if len(batch)<500: break
            offset+=500
        # The app's identity store is authoritative. Never invent/log in a cloud identity.
        with connect() as db:
            identities={r['id']:r['demo'] for r in db.execute('SELECT id,demo FROM users')}
        return [{'id':r['owner_id'],'demo':identities[r['owner_id']],'profile':json.dumps((r.get('o2c_general_profiles') or {}).get('data',{})),'data':json.dumps(r['data']),'visible':r['visible']} for r in rows if r['owner_id'] in identities]

def store():
    name=os.getenv('PROFILE_STORE','sqlite')
    if name=='sqlite': return SQLiteProfiles()
    if name=='supabase': return SupabaseProfiles()
    raise Problem('PROFILE_STORE inválido. / Invalid PROFILE_STORE.',503)

def status():
    name=os.getenv('PROFILE_STORE','sqlite')
    configured=name=='sqlite' or bool(os.getenv('SUPABASE_URL') and (os.getenv('SUPABASE_SECRET_KEY') or os.getenv('SUPABASE_SERVICE_ROLE_KEY')))
    return {'provider':name,'configured':configured,'verified_live':False if name=='supabase' else True}
