"""CLI sub-commands — registered onto the main click group on import."""
from __future__ import annotations

import click

from eaccode.cli import main
from eaccode.cli._output import print_error, print_info, print_success
from eaccode.config.paths import EaccodePaths

# ------------------------------------------------------------------ sessions

@main.group()
def sessions() -> None:
    """Manage sessions (list, resume, search, delete)."""


@sessions.command("list")
@click.option("--limit", default=20, help="Max sessions to show")
def sessions_list(limit: int) -> None:
    """List recent sessions."""
    import asyncio

    from eaccode.sessions.store import SessionStore

    paths = EaccodePaths()
    store = SessionStore(paths.sessions_dir / "sessions.db")
    for s in asyncio.run(store.list_sessions(limit=limit)):
        cwd = s.metadata.get("cwd", "")
        print_info(f"  {s.id[:12]}  {s.title:40s} {s.updated_at[:19]}  {cwd}")


@sessions.command("search")
@click.argument("query")
def sessions_search(query: str) -> None:
    """Full-text search across all sessions."""
    import asyncio

    from eaccode.sessions.search import search_sessions
    from eaccode.sessions.store import SessionStore

    paths = EaccodePaths()
    store = SessionStore(paths.sessions_dir / "sessions.db")
    for h in asyncio.run(search_sessions(store, query)):
        print_info(f"  [{h.title}] {h.session_id}")
        print_info(f"    {h.snippet}")


@sessions.command("delete")
@click.argument("session_id")
def sessions_delete(session_id: str) -> None:
    """Delete a session."""
    import asyncio

    from eaccode.sessions.store import SessionStore

    paths = EaccodePaths()
    store = SessionStore(paths.sessions_dir / "sessions.db")
    ok = asyncio.run(store.delete(session_id))
    if ok:
        print_success("✓ deleted")
    else:
        print_error("✗ session not found")


