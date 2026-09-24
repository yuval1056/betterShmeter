import asyncio
import sqlite3
import threading
from datetime import datetime, timezone

from app.models.schemas import Message

_EMPTY_CONTENT_FALLBACK = "[empty response omitted]"


class MessageRepository:
    """Owns the single shared SQLite connection for the process. All writes
    go through `_lock` so they're serialized even though FastAPI may be
    handling requests concurrently -- this only works because callers all
    share one instance (constructed once in main.py), not one per request."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._lock = threading.Lock()

    def _save_message_sync(
        self, user_id: str, role: str, content: str, conversation_id: str | None
    ) -> Message:
        # Last-resort guard: an empty assistant message must never reach
        # storage, since replaying it as history can 400 on some proxies.
        if not content or not content.strip():
            content = _EMPTY_CONTENT_FALLBACK
        created_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO messages (user_id, conversation_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, conversation_id, role, content, created_at),
            )
            self._conn.commit()
            message_id = cursor.lastrowid
        return Message(
            id=message_id,
            user_id=user_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=created_at,
        )

    def _get_history_sync(self, user_id: str, limit: int | None) -> list[Message]:
        with self._lock:
            if limit is None:
                rows = self._conn.execute(
                    "SELECT id, user_id, role, content, created_at, conversation_id FROM messages "
                    "WHERE user_id = ? ORDER BY id ASC",
                    (user_id,),
                ).fetchall()
            else:
                # Fetch the most recent N in reverse, then flip back to
                # chronological order -- callers always get oldest->newest.
                rows = self._conn.execute(
                    "SELECT id, user_id, role, content, created_at, conversation_id FROM messages "
                    "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
                rows = list(reversed(rows))
        return [
            Message(
                id=row[0],
                user_id=row[1],
                role=row[2],
                content=row[3],
                created_at=row[4],
                conversation_id=row[5],
            )
            for row in rows
        ]

    def _clear_history_sync(self, user_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            self._conn.commit()

    async def save_message(
        self, user_id: str, role: str, content: str, conversation_id: str | None = None
    ) -> Message:
        return await asyncio.to_thread(
            self._save_message_sync, user_id, role, content, conversation_id
        )

    async def get_history(self, user_id: str, limit: int | None = None) -> list[Message]:
        return await asyncio.to_thread(self._get_history_sync, user_id, limit)

    async def clear_history(self, user_id: str) -> None:
        await asyncio.to_thread(self._clear_history_sync, user_id)
