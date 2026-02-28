PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS posts (
    post_id TEXT PRIMARY KEY,
    post_type TEXT NOT NULL,
    author_id TEXT,
    author_name TEXT,
    created_at TEXT,
    first_captured_at TEXT NOT NULL,
    last_captured_at TEXT NOT NULL,
    content_text TEXT,
    content_html TEXT,
    source_post_id TEXT,
    visible_status TEXT NOT NULL,
    raw_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS post_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    raw_hash TEXT NOT NULL,
    FOREIGN KEY(post_id) REFERENCES posts(post_id)
);

CREATE INDEX IF NOT EXISTS idx_post_snapshots_post_id_captured
ON post_snapshots(post_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS poll_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    fetched_count INTEGER NOT NULL,
    new_count INTEGER NOT NULL,
    updated_count INTEGER NOT NULL,
    success INTEGER NOT NULL,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS deletion_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    last_seen_at TEXT,
    UNIQUE(post_id, reason)
);

CREATE TABLE IF NOT EXISTS meta_kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
