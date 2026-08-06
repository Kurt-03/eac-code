"""Session persistence (Task 5.2) — SQLite store for conversation history."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from eaccode.llm.models import Message


class Session(BaseModel):
    id: str
    title: str
    messages: list[Message]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SessionStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    messages TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # FTS5 index for session search (Task 6.6)
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
                USING fts5(session_id UNINDEXED, title, body)
                """
            )

    async def save(
        self,
        title: str,
        messages: list[Message],
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        now = datetime.now().isoformat()
        msgs_json = json.dumps([m.model_dump(mode="json") for m in messages])
        meta_json = json.dumps(metadata or {})
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, messages, metadata, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, "
                "messages=excluded.messages, updated_at=excluded.updated_at",
                (sid, title, msgs_json, meta_json, now, now),
            )
            self._index_messages(conn, sid, title, messages)
        return sid

    @staticmethod
    def _index_messages(conn: sqlite3.Connection, sid: str, title: str, messages: list[Message]) -> None:
        """Refresh the FTS index for one session (delete + reinsert)."""
        conn.execute("DELETE FROM messages_fts WHERE session_id = ?", (sid,))
        body = "\n".join(m.text for m in messages if m.text)
        if body.strip():
            conn.execute(
                "INSERT INTO messages_fts (session_id, title, body) VALUES (?, ?, ?)",
                (sid, title, body[: 500_000]),
            )

    async def load(self, session_id: str) -> Session:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if not row:
            raise KeyError(session_id)
        return self._row_to_session(row)

    async def list_sessions(self, limit: int = 20) -> list[Session]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_session(r) for r in rows]

    async def delete(self, session_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cur.rowcount > 0

    def _row_to_session(self, row: sqlite3.Row | tuple) -> Session:
        get = lambda i: row[i]  # noqa: E731
        return Session(
            id=get(0),
            title=get(1),
            messages=[Message.model_validate(m) for m in json.loads(get(2))],
            metadata=json.loads(get(3)),
            created_at=datetime.fromisoformat(get(4)),
            updated_at=datetime.fromisoformat(get(5)),
        )
