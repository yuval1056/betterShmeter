import sqlite3
from pathlib import Path

from app.core.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    conversation_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_user_id_id ON messages (user_id, id);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON conversations (user_id, updated_at);
"""


def create_connection() -> sqlite3.Connection:
    """One connection for the whole process. Callers must serialize writes
    themselves (see storage.repository) -- sqlite3 connections are not
    safely shared across threads without external locking."""
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    # Databases created before conversation ids existed lack the column.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    if "conversation_id" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN conversation_id TEXT")
    # Created here rather than in _SCHEMA because the column may be added above.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id, id)"
    )
    conn.commit()
    return conn
