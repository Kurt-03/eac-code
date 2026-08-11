"""Hook system (P0.10) — local shell hooks at agent lifecycle points.

Hooks are executable scripts (``.sh`` / any executable) in the hooks
directory (``config_dir/hooks/``). Naming convention:

    pre_tool_use.sh   — before every tool call
    post_tool_use.sh  — after every tool call (stdout spills into the result)
    session_start.sh  — once when the REPL session starts
    session_end.sh    — once when it ends

Five events total (Hermes has 12+): PreToolUse, PostToolUse,
SessionStart, SessionEnd. Hooks run with a timeout and their failures
never break the agent — they are advisory by design.
"""

from __future__ import annotations

from pathlib import Path

EVENTS = ("pre_tool_use", "post_tool_use", "session_start", "session_end")


def discover_hooks(hooks_dir: Path) -> list[Path]:
    """Every hook script in the hooks directory (sorted, any extension)."""
    if not hooks_dir.is_dir():
        return []
    return sorted(
        p for p in hooks_dir.iterdir()
        if p.is_file() and not p.name.startswith(".")
    )


def hook_for_event(hooks_dir: Path, event: str) -> list[Path]:
    """Hooks matching *event*: ``<event>.sh``, ``<event>.*``, ``<event>``."""
    if event not in EVENTS:
        return []
    if not hooks_dir.is_dir():
        return []
    matches = [
        p for p in hooks_dir.iterdir()
        if p.is_file()
        and (p.stem == event or p.name == event)
        and not p.name.startswith(".")
    ]
    return sorted(matches)
