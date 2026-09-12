"""PostgreSQL connection for all application tables in the private o2c_app schema.

The existing repository queries use qmark placeholders. This small adapter only
supports those fixed application queries, not arbitrary SQL supplied by clients.
"""
import re


def postgres_sql(query):
    if query.strip().upper() == 'BEGIN IMMEDIATE':
        # Serialize invitation creation (including opposite-direction invites).
        return 'LOCK TABLE invitations IN SHARE ROW EXCLUSIVE MODE'
    ignore = bool(re.match(r'\s*INSERT OR IGNORE INTO\b', query, re.I))
    query = re.sub(r'\bINSERT OR IGNORE INTO\b', 'INSERT INTO', query, flags=re.I)
    # Preserve SQL string literals, including escaped single quotes.
    chunks = re.split(r"('(?:''|[^'])*')", query)
    query = ''.join(c if i % 2 else c.replace('?', '%s') for i, c in enumerate(chunks))
    if ignore:
        query = query.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
    return query


class PostgresDatabase:
    def __enter__(self):
        from backend.adapters.postgres_profiles import configuration
        from backend.modules.auth import Problem
        import psycopg
        from psycopg.rows import dict_row
        dsn, ca, ready = configuration()
        if not ready:
            raise Problem('Configura SUPABASE_DB_URL y SUPABASE_DB_CA.', 503)
        try:
            self.db = psycopg.connect(dsn, sslmode='verify-full', sslrootcert=str(ca),
                                     connect_timeout=10, row_factory=dict_row)
            self.db.execute('SET LOCAL search_path TO o2c_app')
            self.db.execute("SET LOCAL statement_timeout = '10s'")
            return self
        except psycopg.Error:
            if hasattr(self, 'db'): self.db.close()
            raise Problem('Supabase no disponible. No se usó otra base de datos.', 503) from None

    def execute(self, query, parameters=()):
        return self.db.execute(postgres_sql(query), parameters)

    def __exit__(self, kind, value, traceback):
        from backend.modules.auth import Problem
        import psycopg
        try:
            if kind: self.db.rollback()
            else: self.db.commit()
        except psycopg.Error:
            raise Problem('No se pudo confirmar la operación en Supabase.', 503) from None
        finally:
            self.db.close()
        if kind and issubclass(kind, psycopg.IntegrityError):
            raise Problem('Los datos entran en conflicto con un registro existente.', 409) from None
        if kind and issubclass(kind, psycopg.Error):
            raise Problem('No se pudo completar la operación en Supabase.', 503) from None
        return False
