"""TLS-verified PostgreSQL profile repository; authorization stays in the app API."""
import json
import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from backend.db import connect as local_connect
from backend.modules.auth import Problem

ROOT=Path(__file__).resolve().parents[2]


def configuration():
    dsn=os.getenv('SUPABASE_DB_URL','')
    ca=Path(os.getenv('SUPABASE_DB_CA','supabase/certs/prod-ca-2021.crt'))
    if not ca.is_absolute():ca=ROOT/ca
    try:
        parsed=urlsplit(dsn)
        valid=parsed.scheme in ('postgres','postgresql') and parsed.hostname and parsed.username and parsed.password and ca.is_file()
    except ValueError:
        valid=False
    return dsn,ca,bool(valid)


@contextmanager
def connection(read_only=False):
    dsn,ca,configured=configuration()
    if not configured:raise Problem('Configura SUPABASE_DB_URL y SUPABASE_DB_CA. / Configure SUPABASE_DB_URL and SUPABASE_DB_CA.',503)
    try:
        import psycopg
        with psycopg.connect(dsn,sslmode='verify-full',sslrootcert=str(ca),connect_timeout=10) as db:
            # Poolers may ignore startup options. Set the actual transaction mode.
            db.read_only=read_only
            db.execute("SET LOCAL statement_timeout = '10s'")
            yield db
    except Exception:
        raise Problem('PostgreSQL no disponible. Verifica conexión y esquema. No se guardó en SQLite. / PostgreSQL unavailable. Check connection and schema. No SQLite fallback write occurred.',503) from None


class PostgresProfiles:
    name='postgres'
    def __init__(self,connection_factory=None):
        self.connection=connection_factory or connection
    def get(self,user_id,event):
        with self.connection(read_only=True) as db:
            row=db.execute('''SELECT g.data, e.data, e.visible
                FROM public.o2c_general_profiles g
                LEFT JOIN public.o2c_event_profiles e ON e.owner_id=g.owner_id AND e.event_id=%s
                WHERE g.owner_id=%s''',(event,user_id)).fetchone()
        if not row:return {'visible':True,'saved':False}
        general,data,visible=row
        return {**general,**(data or {}),'visible':visible if data is not None else True,'saved':data is not None}
    def save(self,user_id,event,general,data,visible):
        with self.connection() as db:
            db.execute('SELECT public.o2c_save_profile(%s,%s,%s::jsonb,%s::jsonb,%s)',
                       (user_id,event,json.dumps(general),json.dumps(data),visible))
    def participants(self,event):
        with local_connect() as db:
            identities={r['id']:r['demo'] for r in db.execute('SELECT id,demo FROM users')}
        if not identities:return []
        with self.connection(read_only=True) as db:
            rows=db.execute('''SELECT e.owner_id,g.data,e.data,e.visible
                FROM public.o2c_event_profiles e
                JOIN public.o2c_general_profiles g ON g.owner_id=e.owner_id
                WHERE e.event_id=%s AND e.owner_id=ANY(%s)''',(event,list(identities))).fetchall()
        return [{'id':uid,'demo':identities[uid],'profile':json.dumps(general),'data':json.dumps(data),'visible':visible}
                for uid,general,data,visible in rows]
