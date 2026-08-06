"""Project context discovery (Task 6.2) — like Hermes: parent walk to the
git root for EACCODE.md, first match wins, 20K cap, injection scanner."""
from __future__ import annotations

from pathlib import Path

from eaccode.memory.scanner import scan_for_injection

MAX_CHARS = 20_000

# (filename, parent-walk allowed?) — EACCODE.md is hierarchical, the rest cwd-only
_CONTEXT_FILES = [
    (".eaccode.md", True),
    ("EACCODE.md", True),
    ("AGENTS.md", False),
    ("CLAUDE.md", False),
    (".cursorrules", False),
]


def discover_project_context(workdir: Path) -> str:
    """First-match-wins discovery, parent walk up to the git root."""
    for name, walk in _CONTEXT_FILES:
        path = _find(workdir, name, walk)
        if path is not None:
            return _load_capped(path)
    return ""


def _find(start: Path, name: str, walk: bool) -> Path | None:
    cur = start.resolve()
    while True:
        candidate = cur / name
        if candidate.exists():
            return candidate
        if not walk or cur.parent == cur or (cur / ".git").exists():
            return None
        cur = cur.parent


def _load_capped(path: Path) -> str:
    text = scan_for_injection(path.read_text(encoding="utf-8", errors="replace"))
    prefix = f"# From {path.name}\n\n"
    marker = "\n[...truncated...]\n"
    budget = MAX_CHARS - len(prefix) - len(marker) - 1  # -1: trailing newline
    if len(text) <= budget:
        return prefix + text + "\n"
    head = text[: budget * 2 // 3]
    tail = text[-(budget - len(head)) :]
    return prefix + head + marker + tail + "\n"
