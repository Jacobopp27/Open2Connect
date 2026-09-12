"""Explicit, atomic migration of the configured local DB and cloud profiles.

Run --check first, then --apply. Keeps source tables and a consistent SQLite backup.
Never prints records, passwords, tokens, or connection strings.
"""
import argparse
import json
import os
import sqlite3
import time
from pathlib import Path
from backend.local import load_env

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('users','events','profiles','sessions','mcp_tokens','invitations','blocks','notifications','checkins','encuentros')


def migrate(apply=False):
    load_env(ROOT / '.env')
    import psycopg
    from psycopg import sql
    from backend.adapters.postgres_profiles import configuration
    dsn, ca, ready = configuration()
    if not ready: raise RuntimeError('Missing database configuration')
    source = Path(os.getenv('OPEN2CONNECT_DB', str(ROOT/'data/open2connect.db'))).resolve()
    records = {}
    if source.exists():
        with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as local:
            local.row_factory = sqlite3.Row
            if apply:
                backup = ROOT/'data'/'backups'/f'before-supabase-{time.time_ns()}.db'
                backup.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(backup) as dest: local.backup(dest)
                backup.chmod(0o600)
            for table in TABLES:
                if local.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table',table)).fetchone():
                    records[table] = [dict(r) for r in local.execute('SELECT * FROM '+table)]
    with psycopg.connect(dsn, sslmode='verify-full', sslrootcert=str(ca), connect_timeout=10) as remote:
        remote.execute("SET LOCAL statement_timeout = '60s'")
        remote.execute('SELECT pg_advisory_xact_lock(2026091202)')
        existing = remote.execute("SELECT to_regclass('o2c_app.users')").fetchone()[0]
        if existing:
            raise RuntimeError('Target application schema already exists; do not reimport over live data')
        report = {'source_counts':{t:len(r) for t,r in records.items()},'applied':False}
        if not apply:
            remote.rollback()
            return report
        remote.execute((ROOT/'supabase/migrations/202609120002_app_database.sql').read_text(), prepare=False)
        for table in TABLES:
            for record in records.get(table, []):
                cols=list(record)
                statement=sql.SQL('INSERT INTO o2c_app.{} ({}) VALUES ({}) ON CONFLICT DO NOTHING').format(
                    sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,cols)),sql.SQL(',').join(sql.Placeholder() for _ in cols))
                remote.execute(statement,list(record.values()))
        # Cloud profiles were the selected source of truth in the preceding setup.
        # Preserve their values over stale SQLite copies, only for known identities.
        cloud = remote.execute("SELECT to_regclass('public.o2c_general_profiles')").fetchone()[0]
        if cloud:
            remote.execute('''UPDATE o2c_app.users u SET profile=g.data::text
                FROM public.o2c_general_profiles g WHERE g.owner_id=u.id''')
            remote.execute('''INSERT INTO o2c_app.profiles(user_id,event_id,data,visible)
                SELECT e.owner_id,e.event_id,e.data::text,CASE WHEN e.visible THEN 1 ELSE 0 END
                FROM public.o2c_event_profiles e JOIN o2c_app.users u ON u.id=e.owner_id
                JOIN o2c_app.events v ON v.id=e.event_id
                ON CONFLICT(user_id,event_id) DO UPDATE SET data=excluded.data,visible=excluded.visible''')
        report['target_counts']={t:remote.execute(sql.SQL('SELECT count(*) FROM o2c_app.{}').format(sql.Identifier(t))).fetchone()[0] for t in TABLES}
        report['applied']=True
        return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try: print(json.dumps(migrate(args.apply)))
    except Exception as exc:
        # Exception details from providers may contain private records/credentials.
        print(json.dumps({'applied':False,'error_type':type(exc).__name__,
                          'error':'Migration stopped; source data retained. Check connectivity, constraints and target schema.'}))
        raise SystemExit(1)
