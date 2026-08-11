"""CLI sub-commands — registered onto the main click group on import."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

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
@click.option("--since", default=None, help="Only sessions updated after "
                                             "this date (YYYY-MM-DD)")
@click.option("--query", default=None, help="Text filter on title (case-insensitive)")
def sessions_list(limit: int, since: str | None, query: str | None) -> None:
    """List recent sessions (D.4: --since/--query filters)."""
    import asyncio

    from eaccode.sessions.store import SessionStore

    paths = EaccodePaths()
    store = SessionStore(paths.sessions_dir / "sessions.db")
    since_ts: datetime | None = None
    if since:
        since_ts = _parse_since(since)
        if since_ts is None:
            print_error(f"Invalid --since date: {since!r} "
                        "(use YYYY-MM-DD or relative like 7d/2w/30d)")
            raise SystemExit(2) from None
    for s in asyncio.run(store.list_sessions(limit=limit)):
        if since_ts:
            try:
                raw = s.updated_at.isoformat() if isinstance(
                    s.updated_at, datetime) else str(s.updated_at)
                updated = datetime.fromisoformat(raw)
                if updated < since_ts:
                    continue
            except ValueError:
                pass
        if query and query.lower() not in s.title.lower():
            continue
        cwd = s.metadata.get("cwd", "")
        # updated_at may be a datetime or ISO string — normalize for display.
        updated_txt = s.updated_at.isoformat() if isinstance(
            s.updated_at, datetime) else str(s.updated_at)
        print_info(f"  {s.id[:12]}  {s.title:40s} {updated_txt[:19]}  {cwd}")


def _parse_since(value: str) -> datetime | None:
    """Parse --since: YYYY-MM-DD or relative (7d, 2w, 30d, 12h)."""

    from datetime import datetime

    value = value.strip()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass
    match = re.fullmatch(r"(\d+)([dhw])", value.lower())
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    delta = (
        timedelta(hours=amount) if unit == "h"
        else timedelta(days=amount) if unit == "d"
        else timedelta(weeks=amount)
    )
    return datetime.now() - delta


@sessions.command("recap")
@click.argument("session_id")
def sessions_recap(session_id: str) -> None:
    """Compact summary of a session's tail (D.5)."""
    import asyncio

    from eaccode.sessions.recap import recap
    from eaccode.sessions.store import SessionStore

    paths = EaccodePaths()
    store = SessionStore(paths.sessions_dir / "sessions.db")
    session = asyncio.run(store.get(session_id))
    if session is None:
        print_error("✗ session not found")
        raise SystemExit(1)
    print_info(recap(session))


@sessions.command("export")
@click.argument("session_id")
@click.option("--format", "fmt", type=click.Choice(["md", "html"]),
              default="md", help="Export format")
@click.option("--out", default=None, help="Output directory "
                                          "(default: ./eaccode-exports)")
def sessions_export(session_id: str, fmt: str, out: str | None) -> None:
    """Export a session to markdown or HTML (D.3)."""
    import asyncio
    from pathlib import Path

    from eaccode.sessions.export import write_export
    from eaccode.sessions.store import SessionStore

    paths = EaccodePaths()
    store = SessionStore(paths.sessions_dir / "sessions.db")
    session = asyncio.run(store.get(session_id))
    if session is None:
        print_error("✗ session not found")
        raise SystemExit(1)
    dest = write_export(session, fmt, Path(out or "eaccode-exports"))
    print_success(f"✓ exported → {dest}")


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


