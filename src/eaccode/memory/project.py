"""Project context discovery (Task 6.2) — parent walk for all context files.

Ported from Hermes' ``prompt_builder.py`` ``_load_agents_md`` chain
semantics: AGENTS.md / CLAUDE.md / .cursorrules are loaded from EVERY
directory from cwd up to the git root (nearest first), not just the
first match — a repo can layer rules (root AGENTS.md + subdir
AGENTS.md). EACCODE.md stays first-match-wins (project-specific).
All files are capped (20K total) and passed through the injection
scanner (Phase H.9).
"""

from __future__ import annotations

from pathlib import Path

from eaccode.memory.scanner import scan_for_injection

MAX_CHARS = 20_000

# (filename, parent-walk allowed?, chain-all or first-match?)
_CONTEXT_FILES = [
    (".eaccode.md", True, False),
    ("EACCODE.md", True, False),
    ("AGENTS.md", True, True),     # chain: load all from cwd → git root
    ("CLAUDE.md", True, True),
    (".cursorrules", True, True),
]


def discover_project_context(workdir: Path | None) -> str:
    """Discover and combine context files, nearest-first.

    EACCODE.md/.eaccode.md: first match wins (project identity).
    AGENTS.md/CLAUDE.md/.cursorrules: ALL matches from cwd up to the
    git root are loaded (nearest first) — the layered-rules pattern.
    """
    sections: list[str] = []
    for name, walk, chain in _CONTEXT_FILES:
        paths = _find_all(workdir, name, walk, chain)
        for path in paths:
            sections.append(_load_capped(path))
    return "\n".join(sections)


def _find_all(start: Path | None, name: str, walk: bool, chain: bool) -> list[Path]:
    """Find context files. chain=True → every match up to the git root;
    otherwise first match wins."""
    found: list[Path] = []
    if start is None:
        start = Path.cwd()
    cur = start.resolve()
    while True:
        candidate = cur / name
        if candidate.exists():
            found.append(candidate)
            if not chain:
                return found
        if cur.parent == cur or (cur / ".git").exists():
            return found
        if not walk:
            return found
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
