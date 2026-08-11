"""CLI entry point (Task 1.4).

Command hierarchy (see plan, section "CLI Command Tree"):
    eaccode                     → REPL (Phase 7, currently a hint)
    eaccode paths               → show XDG paths
    eaccode providers add/list/remove/set-default
    eaccode config show/set     → show/change settings
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from eaccode._subprocess_compat import suppress_platform_ver_console

# Windows: stub platform._syscmd_ver before heavyweight imports — many
# dependencies touch platform.uname() at import time, which otherwise
# flashes a `cmd /c ver` console window in the REPL (Phase A.5).
suppress_platform_ver_console()

from eaccode.config.paths import EaccodePaths  # noqa: E402  (after guard)


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0", prog_name="eaccode")
@click.option("--continue", "continue_session", is_flag=True,
              help="Resume the most recent session in the REPL")
@click.option("--resume", "resume_id", default=None,
              help="Resume a session by ID in the REPL")
@click.pass_context
def main(ctx: click.Context, continue_session: bool, resume_id: str | None) -> None:
    """eaccode — autonomous coding agent (BYOK)."""
    if ctx.invoked_subcommand is None:
        if not sys.stdin.isatty():
            click.echo(
                "REPL requires an interactive terminal. "
                "Use: eaccode run <prompt> (headless)"
            )
            return
        from eaccode.ui.repl import run_repl

        initial_messages = None
        workdir = None
        if continue_session or resume_id:
            import asyncio

            from eaccode.sessions.store import SessionStore

            store = SessionStore(EaccodePaths().sessions_dir / "sessions.db")
            session = None
            if resume_id:
                session = asyncio.run(store.load(resume_id))
            else:
                recent = asyncio.run(store.list_sessions(limit=1))
                if recent:
                    session = asyncio.run(store.load(recent[0].id))
            if session:
                initial_messages = [
                    {"role": m.role.value, "content": m.text}
                    for m in session.messages
                    if m.role.value in ("user", "assistant") and m.text
                ]
                workdir = session.metadata.get("cwd") or None
                click.echo(f"Resumed session: {session.title}")
        run_repl(workdir=Path(workdir) if workdir else None,
                 initial_messages=initial_messages)


@main.command()
def paths() -> None:
    """Show resolved config/data paths."""
    p = EaccodePaths()
    click.echo(f"config:    {p.config_dir}")
    click.echo(f"data:      {p.data_dir}")
    click.echo(f"cache:     {p.cache_dir}")
    click.echo(f"sessions:  {p.sessions_dir}")
    click.echo(f"memory:    {p.memory_dir}")
    click.echo(f"skills:    {p.skills_dir}")



# Sub-command registration (import side effects register on `main`) —
# these must run after `main` is defined, hence the late imports
from eaccode.cli import (  # noqa: E402
    commands_computer,  # noqa: F401
    commands_config,  # noqa: F401
    commands_cron,  # noqa: F401
    commands_curator,  # noqa: F401
    commands_mcp,  # noqa: F401
    commands_providers,  # noqa: F401
    commands_queue,  # noqa: F401
    commands_sessions,  # noqa: F401
    commands_skills,  # noqa: F401
    commands_utility,  # noqa: F401
)
