import os
import sqlite3
from pathlib import Path

from contextlib import contextmanager

DB_PATH = os.environ.get('OPEN2CONNECT_DB', str(Path(__file__).resolve().parent.parent / 'data' / 'open2connect.db'))

@contextmanager
def connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=5000')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
          profile TEXT NOT NULL DEFAULT '{}', demo INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS mcp_tokens (hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), event_id TEXT NOT NULL, expires REAL NOT NULL, session_token TEXT NOT NULL REFERENCES sessions(token) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, name TEXT NOT NULL, location TEXT NOT NULL, description TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS profiles (
          user_id TEXT REFERENCES users(id), event_id TEXT REFERENCES events(id), data TEXT NOT NULL,
          visible INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(user_id,event_id));
        CREATE TABLE IF NOT EXISTS invitations (
          id TEXT PRIMARY KEY, event_id TEXT REFERENCES events(id), sender TEXT REFERENCES users(id),
          recipient TEXT REFERENCES users(id), status TEXT NOT NULL, created REAL NOT NULL,
          UNIQUE(event_id,sender,recipient), CHECK(sender != recipient));
        CREATE TABLE IF NOT EXISTS blocks (
          user_id TEXT REFERENCES users(id), target TEXT REFERENCES users(id), PRIMARY KEY(user_id,target));
        CREATE TABLE IF NOT EXISTS notifications (
          id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), message TEXT NOT NULL, created REAL NOT NULL);
        ''')
        db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?)', ('medellin-2026', 'Agents Everywhere · Medellín', 'Medellín, Colombia', '12 septiembre 2026 · Hackatón y conexiones con propósito'))
