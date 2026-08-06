"""session_search agent tool (Task 6.6) — learn from past sessions."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from eaccode.sessions.search import search_sessions
from eaccode.sessions.store import SessionStore
from eaccode.tools.base import Tool, ToolContext, ToolResult


class SessionSearchInput(BaseModel):
    query: str = Field(description="Search query (terms to find in past sessions)")
    limit: int = Field(default=5, description="Max hits to return")


class SessionSearchTool(Tool):
    name = "session_search"
    description = (
        "Search past sessions for previous solutions, decisions, and errors. "
        "Use before answering questions about past work."
    )
    input_model = SessionSearchInput
    requires_permission = False

    async def run(self, input: SessionSearchInput, ctx: ToolContext) -> ToolResult:
        db = ctx.config.get("sessions_db") if isinstance(ctx.config, dict) else None
        if not db:
            from eaccode.config.paths import EaccodePaths

            db = EaccodePaths().sessions_dir / "sessions.db"
        store = SessionStore(Path(db))
        hits = await search_sessions(store, input.query, limit=input.limit)
        if not hits:
            return ToolResult(content="No matching past sessions found.")
        lines = []
        for h in hits:
            lines.append(f"[{h.title}] {h.session_id}\n  {h.snippet}")
        return ToolResult(content="\n".join(lines))
