import asyncio
import sqlite3
import threading
from datetime import datetime, timezone

from app.models.schemas import Conversation, Message

_EMPTY_CONTENT_FALLBACK = "[empty response omitted]"
_TITLE_MAX_LEN = 50
_DEFAULT_TITLE = "New chat"


class MessageRepository:
    """Owns the single shared SQLite connection for the process. All writes
    go through `_lock` so they're serialized even though FastAPI may be
    handling requests concurrently -- this only works because callers all
    share one instance (constructed once in main.py), not one per request."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._lock = threading.Lock()

    def _touch_conversation(
        self, user_id: str, conversation_id: str, role: str, content: str, now: str
    ) -> None:
        """Create the conversation on its first message (titled after it) and
        bump updated_at. The caller holds `_lock` and commits."""
        title = " ".join(content.split())[:_TITLE_MAX_LEN] if role == "user" else ""
        self._conn.execute(
            "INSERT OR IGNORE INTO conversations (id, user_id, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (conversation_id, user_id, title or _DEFAULT_TITLE, now, now),
        )
        self._conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ? AND user_id = ?",
            (now, conversation_id, user_id),
        )

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
            message_id = cursor.lastrowid
            if conversation_id:
                self._touch_conversation(user_id, conversation_id, role, content, created_at)
            self._conn.commit()
        return Message(
            id=message_id,
            user_id=user_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=created_at,
        )

    def _get_history_sync(
        self, user_id: str, limit: int | None, conversation_id: str | None
    ) -> list[Message]:
        # Scope to one conversation when given, else to all of the user's messages.
        where = "user_id = ?"
        params: tuple = (user_id,)
        if conversation_id:
            where += " AND conversation_id = ?"
            params += (conversation_id,)
        columns = "id, user_id, role, content, created_at, conversation_id"
        with self._lock:
            if limit is None:
                rows = self._conn.execute(
                    f"SELECT {columns} FROM messages WHERE {where} ORDER BY id ASC",
                    params,
                ).fetchall()
            else:
                # Fetch the most recent N in reverse, then flip back to
                # chronological order -- callers always get oldest->newest.
                rows = self._conn.execute(
                    f"SELECT {columns} FROM messages WHERE {where} ORDER BY id DESC LIMIT ?",
                    (*params, limit),
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
            self._conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
            self._conn.commit()

    def _list_conversations_sync(self, user_id: str) -> list[Conversation]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations "
                "WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [
            Conversation(id=r[0], title=r[1], created_at=r[2], updated_at=r[3]) for r in rows
        ]

    def _delete_conversation_sync(self, user_id: str, conversation_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM messages WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            )
            self._conn.execute(
                "DELETE FROM conversations WHERE user_id = ? AND id = ?",
                (user_id, conversation_id),
            )
            self._conn.commit()

    async def save_message(
        self, user_id: str, role: str, content: str, conversation_id: str | None = None
    ) -> Message:
        return await asyncio.to_thread(
            self._save_message_sync, user_id, role, content, conversation_id
        )

    async def get_history(
        self, user_id: str, limit: int | None = None, conversation_id: str | None = None
    ) -> list[Message]:
        return await asyncio.to_thread(self._get_history_sync, user_id, limit, conversation_id)

    async def clear_history(self, user_id: str) -> None:
        await asyncio.to_thread(self._clear_history_sync, user_id)

    async def list_conversations(self, user_id: str) -> list[Conversation]:
        return await asyncio.to_thread(self._list_conversations_sync, user_id)

    async def delete_conversation(self, user_id: str, conversation_id: str) -> None:
        await asyncio.to_thread(self._delete_conversation_sync, user_id, conversation_id)
