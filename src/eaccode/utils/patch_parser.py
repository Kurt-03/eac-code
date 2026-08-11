"""V4A patch parser (H.13) — multi-file patch application.

Format (Hermes-style):

    *** Begin Patch
    *** Update File: path/to/file.py
    @@ optional context hint @@
     unchanged context line
    -removed line
    +added line
    *** End Patch

The parser extracts per-file hunks and applies them with exact-match
semantics (fuzzy matching is the caller's job). Whitespace-prefix
conventions follow the reference implementation: context lines carry a
single leading space, removed lines ``-``, added lines ``+``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_BEGIN = re.compile(r"^\*\*\* Begin Patch\s*$")
_END = re.compile(r"^\*\*\* End Patch\s*$")
_FILE = re.compile(r"^\*\*\* Update File:\s*(.+?)\s*$")


@dataclass
class Hunk:
    path: str
    context: str = ""
    lines: list[str] = field(default_factory=list)  # with -/+ markers

    def apply(self, base_dir: Path | None = None) -> bool:
        """Apply the hunk to its file; True when every line matched."""
        target = Path(self.path)
        if base_dir is not None and not target.is_absolute():
            target = base_dir / target
        if not target.exists():
            return False
        text = target.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        changed = 0
        for entry in _hunk_entries(self.lines):
            matched = _apply_entry(lines, entry)
            if not matched:
                return False
            changed += 1
        if changed:
            target.write_text("".join(lines), encoding="utf-8")
        return True


def _hunk_entries(lines: list[str]) -> list[tuple[str, str]]:
    """Split marker lines into (removed, added) replacement pairs."""
    entries: list[tuple[str, str]] = []
    removed: list[str] = []
    added: list[str] = []
    for line in lines:
        if line.startswith("-"):
            if added:
                entries.append(("".join(removed), "".join(added)))
                removed, added = [], []
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
        else:
            if removed or added:
                entries.append(("".join(removed), "".join(added)))
                removed, added = [], []
    if removed or added:
        entries.append(("".join(removed), "".join(added)))
    return entries


def _apply_entry(lines: list[str], entry: tuple[str, str]) -> bool:
    removed, added = entry
    if not removed:
        # Pure insertion: after the first context line (or at the end).
        idx = len(lines)
        for i, line in enumerate(lines):
            if not line.startswith(" "):
                idx = i
                break
        insert = added if added.endswith("\n") else added + "\n"
        lines[idx:idx] = [insert]
        return True
    # Find the removed block as exact consecutive lines. Patch lines
    # carry no newline (splitlines), file lines do — compare stripped.
    removed_lines = removed.splitlines()
    for i in range(len(lines) - len(removed_lines) + 1):
        window = [line.rstrip("\n") for line in lines[i:i + len(removed_lines)]]
        if window == removed_lines:
            replacement = [added] if added.endswith("\n") else [added + "\n"]
            lines[i:i + len(removed_lines)] = replacement if added else []
            return True
    return False


def parse_patch(text: str) -> list[Hunk]:
    """Parse a V4A patch string into hunks (empty list when malformed)."""
    hunks: list[Hunk] = []
    current: Hunk | None = None
    in_patch = False
    for line in text.splitlines():
        if _BEGIN.match(line):
            in_patch = True
            continue
        if _END.match(line):
            in_patch = False
            current = None
            continue
        if not in_patch:
            continue
        file_match = _FILE.match(line)
        if file_match:
            current = Hunk(path=file_match.group(1).strip())
            hunks.append(current)
            continue
        if current is not None:
            if line.startswith("@@") and line.endswith("@@"):
                current.context = line[2:-2].strip()
            else:
                current.lines.append(line)
    return hunks


def apply_patch(text: str, base_dir: Path | None = None) -> dict[str, bool]:
    """Parse + apply; returns {path: applied} for every file touched."""
    results: dict[str, bool] = {}
    for hunk in parse_patch(text):
        results[hunk.path] = hunk.apply(base_dir)
    return results
