import json
import logging
import os
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger("mimir.db")

_db: Optional[aiosqlite.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_uri TEXT,
    title TEXT,
    raw_content TEXT NOT NULL,
    processed_content TEXT,
    synthesis TEXT,
    content_type TEXT DEFAULT 'text',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME,
    processing_status TEXT DEFAULT 'pending',
    processing_stage TEXT,
    retry_count INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0,
    is_starred INTEGER DEFAULT 0,
    word_count INTEGER,
    reading_time_seconds INTEGER
);

CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    parent_id TEXT REFERENCES concepts(id),
    note_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS note_concepts (
    note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    concept_id TEXT REFERENCES concepts(id) ON DELETE CASCADE,
    relevance_score REAL DEFAULT 1.0,
    PRIMARY KEY (note_id, concept_id)
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    description TEXT,
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, entity_type)
);

CREATE TABLE IF NOT EXISTS note_entities (
    note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
    context TEXT,
    PRIMARY KEY (note_id, entity_id)
);

CREATE TABLE IF NOT EXISTS connections (
    id TEXT PRIMARY KEY,
    source_note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    target_note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    connection_type TEXT NOT NULL,
    strength REAL DEFAULT 0.5,
    explanation TEXT,
    discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    surfaced INTEGER DEFAULT 0,
    dismissed INTEGER DEFAULT 0,
    UNIQUE(source_note_id, target_note_id)
);

CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT
);

CREATE TABLE IF NOT EXISTS note_tags (
    note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    tag_id TEXT REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag_id)
);

CREATE TABLE IF NOT EXISTS resurface_queue (
    id TEXT PRIMARY KEY,
    queue_type TEXT NOT NULL,
    note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    connection_id TEXT REFERENCES connections(id),
    reason TEXT NOT NULL,
    priority REAL DEFAULT 0.5,
    scheduled_for DATETIME,
    delivered INTEGER DEFAULT 0,
    clicked INTEGER DEFAULT 0,
    dismissed INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_log (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    details JSON,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    status TEXT DEFAULT 'running',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value JSON NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_usage_log (
    id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms INTEGER,
    cost_usd REAL,
    note_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interest_signals (
    id TEXT PRIMARY KEY,
    signal_type TEXT NOT NULL,
    note_id TEXT,
    query TEXT,
    concept TEXT,
    weight REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_briefs (
    id TEXT PRIMARY KEY,
    brief_date TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL,
    sections JSON,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    delivered_webhook INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS note_actions (
    id TEXT PRIMARY KEY,
    note_id TEXT REFERENCES notes(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    payload JSON NOT NULL,
    status TEXT DEFAULT 'pending',
    dispatched_at DATETIME,
    expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_note_actions_status ON note_actions(status);
CREATE INDEX IF NOT EXISTS idx_note_actions_note ON note_actions(note_id);

CREATE TABLE IF NOT EXISTS bridge_message_log (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    direction TEXT NOT NULL,
    sender_id TEXT,
    intent TEXT,
    text TEXT,
    media_url TEXT,
    status TEXT DEFAULT 'ok',
    response_text TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    raw_payload JSON
);

CREATE TABLE IF NOT EXISTS bridge_sessions (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    user_id TEXT NOT NULL,
    last_note_id TEXT,
    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, user_id)
);

CREATE INDEX IF NOT EXISTS idx_bridge_log_platform ON bridge_message_log(platform);
CREATE INDEX IF NOT EXISTS idx_bridge_log_created ON bridge_message_log(created_at);

CREATE INDEX IF NOT EXISTS idx_notes_status ON notes(processing_status);
CREATE INDEX IF NOT EXISTS idx_notes_source ON notes(source_type);
CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at);
CREATE INDEX IF NOT EXISTS idx_notes_starred ON notes(is_starred) WHERE is_starred = 1;
CREATE INDEX IF NOT EXISTS idx_connections_source ON connections(source_note_id);
CREATE INDEX IF NOT EXISTS idx_connections_target ON connections(target_note_id);
CREATE INDEX IF NOT EXISTS idx_interest_signals_created ON interest_signals(created_at);
CREATE INDEX IF NOT EXISTS idx_interest_signals_type ON interest_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_resurface_queue_delivered ON resurface_queue(delivered);
CREATE INDEX IF NOT EXISTS idx_resurface_queue_scheduled ON resurface_queue(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_concepts_name ON concepts(name);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name, entity_type);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title,
    raw_content,
    processed_content,
    synthesis,
    content='notes',
    content_rowid='rowid'
);
"""

FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS notes_fts_insert AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, raw_content, processed_content, synthesis)
    VALUES (new.rowid, new.title, new.raw_content, new.processed_content, new.synthesis);
END;

CREATE TRIGGER IF NOT EXISTS notes_fts_delete AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, raw_content, processed_content, synthesis)
    VALUES ('delete', old.rowid, old.title, old.raw_content, old.processed_content, old.synthesis);
END;

CREATE TRIGGER IF NOT EXISTS notes_fts_update AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, raw_content, processed_content, synthesis)
    VALUES ('delete', old.rowid, old.title, old.raw_content, old.processed_content, old.synthesis);
    INSERT INTO notes_fts(rowid, title, raw_content, processed_content, synthesis)
    VALUES (new.rowid, new.title, new.raw_content, new.processed_content, new.synthesis);
END;
"""

DEFAULT_SETTINGS = {
    "general": {
        "instance_name": "Mimir",
        "timezone": "America/New_York",
        "language": "en",
    },
    "agent": {
        "brief_enabled": True,
        "brief_time": "07:00",
        "brief_delivery": ["dashboard"],
        "connection_scan_interval_hours": 6,
        "max_llm_calls_per_scan": 50,
        "resurface_enabled": True,
        "spaced_rep_enabled": True,
        "spaced_rep_intervals_days": [1, 3, 7, 14, 30, 60, 90],
    },
    "processing": {
        "llm_model": "gemma3",
        "embedding_model": "nomic-embed-text",
        "chunk_target_tokens": 400,
        "chunk_overlap_tokens": 50,
        "connection_similarity_threshold": 0.75,
        "connection_strength_minimum": 0.5,
        "max_concepts_per_note": 10,
        "max_entities_per_note": 15,
    },
    "capture": {
        "email_enabled": False,
        "file_watch_enabled": True,
        "auto_archive_email": True,
    },
    "notifications": {
        "webhook_url": None,
        "webhook_type": "generic",
    },
    "bridge": {
        "enabled_platforms": [],
        "telegram": {"bot_token": "", "webhook_base_url": "", "user_id": ""},
        "mattermost": {"url": "", "bot_token": "", "channel_id": "", "user_id": ""},
        "outbound_channels": {"daily_brief": [], "connection_alert": [], "resurface": []},
        "security": {"allowed_sender_ids": {"telegram": [], "mattermost": []}},
    },
}


async def init_db(db_path: str) -> None:
    global _db
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    _db = await aiosqlite.connect(db_path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")

    await _db.executescript(SCHEMA)
    await _db.executescript(FTS_SCHEMA)
    await _db.executescript(FTS_TRIGGERS)

    # Seed default settings
    for key, value in DEFAULT_SETTINGS.items():
        await _db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, json.dumps(value)),
        )
    await _db.commit()


async def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None


async def execute(sql: str, params: tuple = ()) -> aiosqlite.Cursor:
    db = await get_db()
    cursor = await db.execute(sql, params)
    await db.commit()
    return cursor


async def execute_many(sql: str, params_list: list[tuple]) -> None:
    db = await get_db()
    await db.executemany(sql, params_list)
    await db.commit()


async def fetch_one(sql: str, params: tuple = ()) -> Optional[dict]:
    db = await get_db()
    cursor = await db.execute(sql, params)
    row = await cursor.fetchone()
    if row is None:
        return None
    return dict(row)


async def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
