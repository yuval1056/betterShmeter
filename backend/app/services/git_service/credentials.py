"""Per-user GitHub credentials, supplied from the frontend and stored in a
local SQLite file (settings.GITHUB_DB_PATH, under the gitignored data/
directory) -- not in .env and not in the chat database. Rows are written
only after the GitHub MCP server has confirmed the token can see the
given repository (see mcp_client.verify_repo).

GitHub no longer accepts account passwords for API access, so a personal
access token is the only secret collected. The token is stored in plain
text, so treat the file like any local secret. If a user hasn't connected
their own account, the server-level values from .env (if any) act as a
fallback."""

import asyncio
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS github_credentials (
    user_id TEXT PRIMARY KEY,
    conversation_id TEXT,
    token TEXT NOT NULL,
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class GitCredentials:
    token: str
    owner: str
    repo: str


_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def _connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = Path(settings.GITHUB_DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(path), check_same_thread=False)
        _conn.executescript(_SCHEMA)
        columns = {row[1] for row in _conn.execute("PRAGMA table_info(github_credentials)")}
        if "conversation_id" not in columns:
            _conn.execute("ALTER TABLE github_credentials ADD COLUMN conversation_id TEXT")
        _conn.commit()
    return _conn


def _save_sync(user_id: str, creds: GitCredentials, conversation_id: str | None) -> None:
    with _lock:
        conn = _connection()
        conn.execute(
            "INSERT INTO github_credentials (user_id, conversation_id, token, owner, repo, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
            "conversation_id=excluded.conversation_id, token=excluded.token, owner=excluded.owner, repo=excluded.repo, "
            "updated_at=excluded.updated_at",
            (user_id, conversation_id, creds.token, creds.owner, creds.repo, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def _load_sync(user_id: str) -> GitCredentials | None:
    with _lock:
        row = (
            _connection()
            .execute("SELECT token, owner, repo FROM github_credentials WHERE user_id = ?", (user_id,))
            .fetchone()
        )
    return GitCredentials(*row) if row else None


def _delete_sync(user_id: str) -> None:
    with _lock:
        conn = _connection()
        conn.execute("DELETE FROM github_credentials WHERE user_id = ?", (user_id,))
        conn.commit()


async def save_credentials(
    user_id: str, creds: GitCredentials, conversation_id: str | None = None
) -> None:
    await asyncio.to_thread(_save_sync, user_id, creds, conversation_id)


async def get_user_credentials(user_id: str) -> GitCredentials | None:
    return await asyncio.to_thread(_load_sync, user_id)


async def delete_credentials(user_id: str) -> None:
    await asyncio.to_thread(_delete_sync, user_id)


async def get_credentials(user_id: str) -> GitCredentials | None:
    """The user's own credentials, else the server-level fallback, else None."""
    creds = await get_user_credentials(user_id)
    if creds:
        return creds
    if settings.GITHUB_PERSONAL_ACCESS_TOKEN:
        return GitCredentials(
            token=settings.GITHUB_PERSONAL_ACCESS_TOKEN,
            owner=settings.GITHUB_OWNER,
            repo=settings.GITHUB_REPO,
        )
    return None
