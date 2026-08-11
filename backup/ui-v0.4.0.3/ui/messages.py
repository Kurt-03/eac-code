"""System message rendering (Phase B.6).

Claude Code / Hermes style: non-fatal events render as compact system
lines — `[ i ]` for info, `[ ! ]` for warnings — instead of ad-hoc red
panels. Red is reserved for genuinely fatal errors (loop crash, agent
raised).
"""

from __future__ import annotations


def write_info(text: str) -> str:
    """Dim info line: `[ i ] text`."""
    return f"[dim][ i ] {text}[/dim]"


def write_warn(text: str) -> str:
    """Yellow warning line: `[ ! ] text`."""
    return f"[yellow][ ! ] {text}[/yellow]"


def write_error(text: str) -> str:
    """Red error line — reserved for fatal errors."""
    return f"[red][ ✗ ] {text}[/red]"
