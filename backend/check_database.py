"""Read-only PostgreSQL connection check. Does not print connection credentials."""
import json
import os
from pathlib import Path
from backend.local import load_env

ROOT=Path(__file__).resolve().parent.parent


def check():
    import psycopg
    load_env(ROOT/'.env')
    dsn=os.getenv('SUPABASE_DB_URL','')
    ca=Path(os.getenv('SUPABASE_DB_CA','supabase/certs/prod-ca-2021.crt'))
    if not ca.is_absolute():ca=ROOT/ca
    if not dsn or not ca.is_file():
        return {'connected':False,'reason':'Configure SUPABASE_DB_URL and SUPABASE_DB_CA'},1
    try:
        with psycopg.connect(dsn,sslmode='verify-full',sslrootcert=str(ca),connect_timeout=10,
                options='-c default_transaction_read_only=on -c statement_timeout=5000') as conn:
            conn.read_only=True
            row=conn.execute("SELECT current_setting('transaction_read_only'), to_regclass('public.o2c_general_profiles') IS NOT NULL, to_regclass('public.o2c_event_profiles') IS NOT NULL").fetchone()
            result={'connected':True,'tls':conn.pgconn.ssl_in_use,'read_only':row[0]=='on',
                    'general_table_exists':row[1],'event_table_exists':row[2]}
            conn.rollback()
            return result,0
    except psycopg.Error as exc:
        msg=str(exc).lower()
        reason=('authentication' if 'password authentication failed' in msg else
                'project_or_user' if 'tenant or user not found' in msg else
                'tls_certificate' if 'certificate' in msg else
                'network' if any(k in msg for k in ['resolve','nodename','timeout','connection refused']) else
                'database_connection')
        return {'connected':False,'reason':reason},1


if __name__=='__main__':
    result,code=check()
    print(json.dumps(result))
    raise SystemExit(code)
