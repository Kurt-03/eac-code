"""Memory provider abstraction (A.10) — interface over the markdown store.

Tools, the curator and future backends talk to ``MemoryProvider``
instead of the concrete ``MarkdownMemoryStore``. The markdown store is
the default implementation; a JSONL-backed provider could slot in later.
"""

from __future__ import annotations

from pathlib import Path

from eaccode.memory.markdown_store import MarkdownMemoryStore


class MemoryProvider:
    """Read/write access to the three memory kinds (memory/user/soul)."""

    def read(self, kind: str, project_hash: str | None = None) -> str: ...

    def add_fact(self, kind: str, fact: str,
                 project_hash: str | None = None) -> None: ...

    def remove_line(self, kind: str, needle: str,
                    project_hash: str | None = None) -> bool: ...

    def replace_fact(self, kind: str, old: str, new: str,
                     project_hash: str | None = None) -> bool: ...


class MarkdownMemoryProvider(MemoryProvider):
    """Default provider — delegates to MarkdownMemoryStore."""

    def __init__(self, memory_dir: Path) -> None:
        self._store = MarkdownMemoryStore(memory_dir)

    def read(self, kind: str, project_hash: str | None = None) -> str:
        return self._store.read(kind, project_hash)

    def add_fact(self, kind: str, fact: str,
                 project_hash: str | None = None) -> None:
        self._store.add_fact(kind, fact, project_hash)

    def remove_line(self, kind: str, needle: str,
                    project_hash: str | None = None) -> bool:
        return self._store.remove_line(kind, needle, project_hash)

    def replace_fact(self, kind: str, old: str, new: str,
                     project_hash: str | None = None) -> bool:
        return self._store.replace_fact(kind, old, new, project_hash)
