-- Unified application storage. Separate private schema; no browser/Data API access.
CREATE SCHEMA IF NOT EXISTS o2c_app;
REVOKE ALL ON SCHEMA o2c_app FROM PUBLIC, anon, authenticated;
SET LOCAL search_path TO o2c_app;

        CREATE TABLE IF NOT EXISTS users (
          id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
          profile TEXT NOT NULL DEFAULT '{}', demo INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires DOUBLE PRECISION NOT NULL);
        CREATE TABLE IF NOT EXISTS mcp_tokens (hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), event_id TEXT NOT NULL, expires DOUBLE PRECISION NOT NULL, session_token TEXT NOT NULL REFERENCES sessions(token) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, name TEXT NOT NULL, location TEXT NOT NULL, description TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS profiles (
          user_id TEXT REFERENCES users(id), event_id TEXT REFERENCES events(id), data TEXT NOT NULL,
          visible INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(user_id,event_id));
        CREATE TABLE IF NOT EXISTS invitations (
          id TEXT PRIMARY KEY, event_id TEXT REFERENCES events(id), sender TEXT REFERENCES users(id),
          recipient TEXT REFERENCES users(id), status TEXT NOT NULL, created DOUBLE PRECISION NOT NULL,
          UNIQUE(event_id,sender,recipient), CHECK(sender != recipient));
        CREATE TABLE IF NOT EXISTS blocks (
          user_id TEXT REFERENCES users(id), target TEXT REFERENCES users(id), PRIMARY KEY(user_id,target));
        CREATE TABLE IF NOT EXISTS notifications (
          id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), message TEXT NOT NULL, created DOUBLE PRECISION NOT NULL);
        
CREATE TABLE IF NOT EXISTS checkins (
 user_id TEXT NOT NULL REFERENCES users(id), event_id TEXT NOT NULL REFERENCES events(id),
 checked_in_at DOUBLE PRECISION NOT NULL, sena TEXT NOT NULL, PRIMARY KEY(user_id,event_id));
CREATE TABLE IF NOT EXISTS encuentros (
 user_a TEXT NOT NULL REFERENCES users(id), user_b TEXT NOT NULL REFERENCES users(id),
 event_id TEXT NOT NULL REFERENCES events(id), confirmado_en DOUBLE PRECISION NOT NULL,
 PRIMARY KEY(user_a,user_b,event_id));

INSERT INTO events VALUES ('medellin-2026','Agents Everywhere · Medellín','Medellín, Colombia','12 septiembre 2026 · Hackatón y conexiones con propósito') ON CONFLICT DO NOTHING;
REVOKE ALL ON ALL TABLES IN SCHEMA o2c_app FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA o2c_app REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
ALTER TABLE o2c_app.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE o2c_app.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE o2c_app.mcp_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE o2c_app.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE o2c_app.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE o2c_app.invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE o2c_app.blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE o2c_app.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE o2c_app.checkins ENABLE ROW LEVEL SECURITY;
ALTER TABLE o2c_app.encuentros ENABLE ROW LEVEL SECURITY;
