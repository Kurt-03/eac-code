"""FTS5 session search (Task 6.6) — find past solutions and decisions."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class SearchHit:
    session_id: str
    title: str
    snippet: str


async def search_sessions(store, query: str, limit: int = 5) -> list[SearchHit]:
    # Quote each term so FTS5 treats it as a literal phrase — raw user input
    # like "zzz-nothing" would otherwise be parsed as column syntax and error.
    fts_query = " AND ".join(f'"{t}"' for t in query.split() if t)
    if not fts_query:
        return []
    with sqlite3.connect(store.db_path) as conn:
        try:
            rows = conn.execute(
                "SELECT session_id, title, "
                "snippet(messages_fts, 2, '[', ']', '...', 5) AS snip "
                "FROM messages_fts WHERE messages_fts MATCH ? ORDER BY rank LIMIT ?",
                (fts_query, limit),
            ).fetchall()
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                return []  # FTS not initialized yet → quietly empty
            raise  # real query errors must not be swallowed
    return [SearchHit(session_id=r[0], title=r[1], snippet=r[2] or "") for r in rows]
