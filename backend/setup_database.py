"""Create empty application tables in Supabase; never read or import old data."""
import json
from pathlib import Path
from backend.local import load_env

ROOT = Path(__file__).resolve().parents[1]


def setup():
    load_env(ROOT / '.env')
    import psycopg
    from backend.adapters.postgres_profiles import configuration
    dsn, ca, ready = configuration()
    if not ready: raise RuntimeError('Missing database configuration')
    with psycopg.connect(dsn, sslmode='verify-full', sslrootcert=str(ca), connect_timeout=10) as db:
        db.execute("SET LOCAL statement_timeout = '30s'")
        db.execute('SELECT pg_advisory_xact_lock(2026091202)')
        if db.execute("SELECT to_regnamespace('o2c_app')").fetchone()[0]:
            raise RuntimeError('Application schema already exists; refusing to overwrite it')
        db.execute((ROOT/'supabase/migrations/202609120002_app_database.sql').read_text(), prepare=False)
        assert db.execute('SELECT count(*) FROM o2c_app.users').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM o2c_app.profiles').fetchone()[0] == 0
    return {'created':True,'schema':'o2c_app','imported_records':0,'seed_events':1}


if __name__ == '__main__':
    try: print(json.dumps(setup()))
    except Exception as exc:
        print(json.dumps({'created':False,'error_type':type(exc).__name__,
                          'error':'Setup stopped; no existing data was modified.'}))
        raise SystemExit(1)
