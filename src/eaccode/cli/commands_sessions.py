"""CLI sub-commands — registered onto the main click group on import."""
from __future__ import annotations

from pathlib import Path

import click

from eaccode.config.paths import EaccodePaths
from eaccode.config.providers import ProviderConfig, load_providers, save_providers
from eaccode.config.settings import PermissionMode, Settings
from eaccode.cli import main

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
        click.echo(f"  {s.id[:12]}  {s.title:40s} {s.updated_at[:19]}  {cwd}")


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
        click.echo(f"  [{h.title}] {h.session_id}")
        click.echo(f"    {h.snippet}")


@sessions.command("delete")
@click.argument("session_id")
def sessions_delete(session_id: str) -> None:
    """Delete a session."""
    import asyncio

    from eaccode.sessions.store import SessionStore

    paths = EaccodePaths()
    store = SessionStore(paths.sessions_dir / "sessions.db")
    ok = asyncio.run(store.delete(session_id))
    click.echo("✓ deleted" if ok else "✗ session not found")


