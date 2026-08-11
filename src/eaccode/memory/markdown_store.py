"""Markdown memory store (P0.3) — MEMORY.md / USER.md / SOUL.md.

Hermes-style plain-markdown memory with hard char budgets:

- ``MEMORY.md`` — project-scoped (``memory_dir/projects/<hash>/``), ≤ 2200
- ``USER.md``   — user-global (``memory_dir/``), ≤ 1375
- ``SOUL.md``   — personality/tone/working-style (``memory_dir/``), ≤ 800

Writes are atomic (temp + rename). Budgets are enforced with a clear
error instead of silent truncation — the caller (tool or slash command)
decides how to shrink. The legacy JSONL fact store stays untouched as an
internal layer; the markdown files are the user-facing memory.
"""

from __future__ import annotations

from pathlib import Path

MEMORY_BUDGET = 2200
USER_BUDGET = 1375
SOUL_BUDGET = 800

KINDS = ("memory", "user", "soul")
_BUDGETS = {"memory": MEMORY_BUDGET, "user": USER_BUDGET, "soul": SOUL_BUDGET}
_FILENAMES = {"memory": "MEMORY.md", "user": "USER.md", "soul": "SOUL.md"}

# A.8: first-run SOUL.md template — tone + working style guidance.
SOUL_TEMPLATE = (
    "# Working Style\n\n"
    "- Be direct and honest; say when something is uncertain.\n"
    "- Verify claims against real sources instead of guessing.\n"
    "- Keep code, comments and CLI text in English.\n"
    "- Prefer small, reviewable changes over big rewrites.\n"
)


class BudgetExceededError(ValueError):
    """Raised when a write would exceed the kind's char budget."""


class MarkdownMemoryStore:
    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = Path(memory_dir)

    # ------------------------------------------------------------ paths

    def _path(self, kind: str, project_hash: str | None = None) -> Path:
        if kind == "memory":
            if not project_hash:
                raise ValueError("MEMORY.md needs a project_hash")
            return self.memory_dir / "projects" / project_hash / _FILENAMES[kind]
        return self.memory_dir / _FILENAMES[kind]

    # ------------------------------------------------------------- read

    def read(self, kind: str, project_hash: str | None = None) -> str:
        """Current content of the file ("" when missing)."""
        path = self._path(kind, project_hash)
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    # ------------------------------------------------------------ write

    def write(self, kind: str, text: str, project_hash: str | None = None) -> None:
        """Atomic write with budget enforcement."""
        budget = _BUDGETS[kind]
        if len(text) > budget:
            raise BudgetExceededError(
                f"{_FILENAMES[kind]} would be {len(text)} chars — budget is "
                f"{budget}. Trim it (e.g. /remember a shorter fact) and retry."
            )
        path = self._path(kind, project_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)

    # ------------------------------------------------------------ edits

    def add_fact(self, kind: str, fact: str,
                 project_hash: str | None = None) -> None:
        """Append ``- fact`` (deduped on exact match) under the budget."""
        current = self.read(kind, project_hash).rstrip()
        lines = [ln for ln in current.splitlines() if ln.strip()]
        normalized = fact.strip().replace("\n", " ")
        if any(ln.lstrip("- ").strip() == normalized for ln in lines):
            return  # already there
        lines.append(f"- {normalized}")
        self.write(kind, "\n".join(lines) + "\n", project_hash)

    def remove_line(self, kind: str, needle: str,
                    project_hash: str | None = None) -> bool:
        """Remove the first line containing *needle*; True when removed."""
        current = self.read(kind, project_hash)
        kept: list[str] = []
        removed = False
        for line in current.splitlines():
            if not removed and needle in line:
                removed = True
                continue
            kept.append(line)
        if removed:
            self.write(kind, "\n".join(kept).rstrip() + ("\n" if kept else ""),
                       project_hash)
        return removed

    def replace_fact(self, kind: str, old: str, new: str,
                     project_hash: str | None = None) -> bool:
        """Replace the first line containing *old*; True when replaced."""
        current = self.read(kind, project_hash)
        replaced = False
        lines: list[str] = []
        for line in current.splitlines():
            if not replaced and old in line:
                lines.append(f"- {new.strip()}")
                replaced = True
                continue
            lines.append(line)
        if replaced:
            self.write(kind, "\n".join(lines).rstrip() + ("\n" if lines else ""),
                       project_hash)
        return replaced

    def trim(self, kind: str, project_hash: str | None = None) -> int:
        """A.12: drop oldest fact lines until the content fits the budget.

        Header lines (starting with ``#``) are protected. Returns the
        number of removed lines (0 when already within budget).
        """
        current = self.read(kind, project_hash)
        budget = _BUDGETS[kind]
        if len(current) <= budget:
            return 0
        lines = [ln for ln in current.splitlines() if ln.strip()]
        headers = [ln for ln in lines if ln.startswith("#")]
        body = [ln for ln in lines if not ln.startswith("#")]
        removed = 0
        while body and len("\n".join([*headers, *body])) > budget:
            body.pop(0)  # oldest first
            removed += 1
        self.write(kind, "\n".join([*headers, *body]) + "\n", project_hash)
        return removed

    # ------------------------------------------------------ first run

    def ensure_first_run(self) -> None:
        """Create the global files with headers when missing (idempotent)."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        templates = {
            "user": "# User Profile\n\n",
            "soul": SOUL_TEMPLATE,
        }
        for kind, header in templates.items():
            path = self._path(kind)
            if not path.exists():
                path.write_text(header, encoding="utf-8")
