"""Diff renderer for the inline permission prompt (Phase B.2 → v0.0.1).

The REPL renders an inline permission question in the transcript. For
write/edit calls, the diff between the current file contents and the
proposed change is shown next to the prompt. The diff is *plain text*
(no Rich markup) — the prompt layer (`tui/render.py`) wraps each line
in the appropriate color span (red ``-``, green ``+``, cyan ``@@``,
blue file headers).

The legacy `PermissionModal` ModalScreen was removed in v0.0.1 (the
REPL never pushed it; the inline question is the only UX path).
"""
from __future__ import annotations

import difflib
from pathlib import Path


def build_unified_diff(old_text: str, new_text: str, path: str = "file") -> str:
    """Render a unified diff between two strings (Phase B.2)."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{path}", tofile=f"b/{path}",
            lineterm="",
        )
    )


def diff_for_write(path: Path, content: str, max_lines: int = 30) -> str | None:
    """Diff for a write call: empty file → content (all additions).

    Returns None when the diff would be huge (cap 30 lines of context).
    """
    if path.exists():
        old = path.read_text(encoding="utf-8", errors="replace")
        diff = build_unified_diff(old, content, str(path))
    else:
        # New file: everything is an addition.
        lines = content.splitlines()
        diff = f"--- a/{path}\n+++ b/{path}\n"
        diff += "\n".join(f"+{ln}" for ln in lines[: max_lines - 4])
        if len(lines) > max_lines - 4:
            diff += f"\n+… ({len(lines) - (max_lines - 4)} more lines)"
        diff = "\n".join([*diff.splitlines()[:max_lines],
                          f"… ({len(diff.splitlines()) - max_lines} more lines)"]) \
            if len(diff.splitlines()) > max_lines else diff
    return diff
