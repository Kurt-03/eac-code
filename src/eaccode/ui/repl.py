"""Legacy entry point — the app now lives in :mod:`eaccode.tui.app`.

Kept as a thin re-export so existing imports (tests, plugins) keep
working. The v0.4.0.3 implementation is archived under
``backup/ui-v0.4.0.3/``.
"""

from __future__ import annotations

from pathlib import Path

from eaccode.tui.app import (  # noqa: F401 (re-export)
    EaccodeApp,
    PermissionAwareInput,
)


def run_repl(workdir: Path | None = None,
             initial_messages: list | None = None) -> None:
    """Run the eaccode TUI (v0.5.0 Hermes-style rebuild)."""
    app = EaccodeApp(workdir=workdir, initial_messages=initial_messages)
    app.run()
