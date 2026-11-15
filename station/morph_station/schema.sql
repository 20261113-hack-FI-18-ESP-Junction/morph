PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
  kind TEXT NOT NULL, id TEXT NOT NULL, session_id TEXT NOT NULL,
  cycle_id TEXT, revision INTEGER NOT NULL CHECK(revision > 0),
  payload TEXT NOT NULL CHECK(json_valid(payload)),
  PRIMARY KEY(kind, id)
);
CREATE INDEX IF NOT EXISTS record_scope ON records(session_id, cycle_id, kind);
CREATE TABLE IF NOT EXISTS events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
  fingerprint TEXT NOT NULL, kind TEXT NOT NULL, entity_id TEXT NOT NULL,
  session_id TEXT NOT NULL, cycle_id TEXT, revision INTEGER NOT NULL,
  occurred_at TEXT NOT NULL, received_at TEXT NOT NULL,
  source_mode TEXT NOT NULL CHECK(source_mode IN ('live','simulation')),
  operation TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE INDEX IF NOT EXISTS event_scope ON events(session_id, sequence);
CREATE TABLE IF NOT EXISTS revisions (
  kind TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL,
  event_id TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload)),
  PRIMARY KEY(kind, id, revision),
  FOREIGN KEY(event_id) REFERENCES events(event_id)
);
CREATE TABLE IF NOT EXISTS request_receipts (
  event_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
  response TEXT NOT NULL CHECK(json_valid(response))
);
