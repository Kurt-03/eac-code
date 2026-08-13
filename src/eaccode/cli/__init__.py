"""CLI entry point (Task 1.4).

Command hierarchy (see plan, section "CLI Command Tree"):
    eaccode                     → REPL (Phase 7, currently a hint)
    eaccode paths               → show XDG paths
    eaccode providers add/list/remove/set-default
    eaccode config show/set     → show/change settings
"""
from __future__ import annotations

import os
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
@click.version_option(version="0.0.1", prog_name="eaccode")
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
        # P0.2 (audit): Directories we never want the agent workdir to land in.
# PowerShell opens in C:\Windows\System32 by default; bash logins can
# land in /etc. When we detect one of these, we fall back to the user's
# home directory with a warning, instead of letting the agent operate
# in a system folder.
_UNSAFE_WORKDIR_PREFIXES_WINDOWS: tuple[str, ...] = (
    r"C:\Windows",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\ProgramData",
)
_UNSAFE_WORKDIR_EXACT_UNIX: tuple[str, ...] = (
    "/", "/etc", "/usr", "/var",
    "/bin", "/sbin", "/boot", "/lib", "/lib64",
)
_UNSAFE_WORKDIR_PREFIX_UNIX: tuple[str, ...] = (
    "/etc/", "/var/", "/usr/", "/boot/", "/lib/", "/lib64/",
)


def _safe_workdir() -> Path | None:
    r"""Pick a safe working directory, or None if Path.cwd() is fine."""
    cwd = Path.cwd()
    cwd_str = str(cwd).replace("/", "\\") if os.name == "nt" else str(cwd)
    cwd_lower = cwd_str.lower()

    bad = False
    if os.name == "nt":
        bad = any(cwd_lower.startswith(p.lower())
                  for p in _UNSAFE_WORKDIR_PREFIXES_WINDOWS)
    else:
        if cwd_lower in _UNSAFE_WORKDIR_EXACT_UNIX or any(cwd_lower.startswith(p)
                 for p in _UNSAFE_WORKDIR_PREFIX_UNIX):
            bad = True

    if not bad:
        return None
    fallback = Path.home()
    click.echo(
        f"[ ! ] workdir looks unsafe ({cwd}); falling back to {fallback}.",
        err=True,
    )
    return fallback





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





# P0.2 (audit): Directories we never want the agent's workdir to land in.
# PowerShell opens in C:\Windows\System32 by default; bash logins can
# land in /etc. When we detect one of these, we fall back to the user's
# home dir and print a one-line warning.
_UNSAFE_WORKDIR_PREFIXES_WINDOWS: tuple[str, ...] = (
    r"C:\Windows",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\ProgramData",
)
_UNSAFE_WORKDIR_EXACT_UNIX: tuple[str, ...] = (
    "/", "/etc", "/usr", "/var",
    "/bin", "/sbin", "/boot", "/lib", "/lib64",
)
_UNSAFE_WORKDIR_PREFIX_UNIX: tuple[str, ...] = (
    "/etc/", "/var/", "/usr/", "/boot/", "/lib/", "/lib64/",
)


def _safe_workdir() -> Path | None:

    cwd = Path.cwd()
    cwd_str = str(cwd).replace("/", "\\") if os.name == "nt" else str(cwd)
    cwd_lower = cwd_str.lower()

    bad = False
    if os.name == "nt":
        bad = any(cwd_lower.startswith(p.lower())
                  for p in _UNSAFE_WORKDIR_PREFIXES_WINDOWS)
    else:
        if cwd_lower in _UNSAFE_WORKDIR_EXACT_UNIX or any(cwd_lower.startswith(p)
                 for p in _UNSAFE_WORKDIR_PREFIX_UNIX):
            bad = True

    if not bad:
        return None
    fallback = Path.home()
    click.echo(
        f"[ ! ] workdir looks unsafe ({cwd}); falling back to {fallback}.",
        err=True,
    )
    return fallback


# Sub-command registration (import side effects register on `main`) —
# these must run after `main` is defined, hence the late imports
from eaccode.cli import (  # noqa: E402
    commands_computer,  # noqa: F401
    commands_config,  # noqa: F401
    commands_cron,  # noqa: F401
    commands_curator,  # noqa: F401
    commands_mcp,  # noqa: F401
    commands_ops,  # noqa: F401
    commands_providers,  # noqa: F401
    commands_queue,  # noqa: F401
    commands_sessions,  # noqa: F401
    commands_setup,  # noqa: F401
    commands_skills,  # noqa: F401
    commands_utility,  # noqa: F401
)
