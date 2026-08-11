"""Permanent command allowlist (P0.9/P0.20) — ~/.eaccode/allowlist.json.

Entries mirror session rules but persist across sessions:

    {"tool": "bash", "pattern": "pytest *", "scope": "always"}

- ``always`` entries are stored in the JSON file.
- ``session`` entries live in memory only (added by P0.20's history
  import; they vanish with the process).

Matching mirrors :class:`~eaccode.permissions.rules.Rule`: the pattern
applies to the command (bash) or path (write/edit/read); tool-only
entries (pattern "*") match every call of that tool. The policy engine
consults the allowlist before the mode default, so an explicit "always"
beats PLAN-mode's deny-by-default — while explicit DENY rules still win
over everything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

ALLOWLIST_FILE = "allowlist.json"


@dataclass(frozen=True)
class AllowlistEntry:
    tool: str  # "bash", "write", "edit", "read", or "*"
    pattern: str = "*"
    scope: str = "always"  # always | session

    def matches(self, tool: str, arguments: dict) -> bool:
        if self.tool != "*" and self.tool != tool:
            return False
        if self.pattern == "*":
            return True
        key = (
            "command"
            if tool == "bash"
            else "path"
            if tool in ("write", "edit", "read")
            else None
        )
        if key is None or key not in arguments:
            return False
        return fnmatch(str(arguments[key]), self.pattern)


def suggest_pattern(tool: str, arguments: dict) -> str:
    """Pattern candidate for a call: bash → '<head> *', files → '*'."""
    if tool == "bash":
        command = str(arguments.get("command", ""))
        head = command.split()[0] if command.split() else "*"
        return f"{head} *"
    return "*"


class AllowlistStore:
    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            from eaccode.config.paths import EaccodePaths

            path = EaccodePaths().config_dir / ALLOWLIST_FILE
        self.path = path
        self._persistent: list[AllowlistEntry] = []
        self._session: list[AllowlistEntry] = []
        self.load()

    # ------------------------------------------------------------ io

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = []
        self._persistent = [
            AllowlistEntry(e["tool"], e.get("pattern", "*"), e.get("scope", "always"))
            for e in raw
            if isinstance(e, dict) and e.get("tool")
        ]

    def save(self) -> None:
        data = [
            {"tool": e.tool, "pattern": e.pattern, "scope": e.scope}
            for e in self._persistent
        ]
        tmp = self.path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass  # best-effort: an unwritable allowlist must not break calls

    # ------------------------------------------------------------ access

    def entries(self) -> list[AllowlistEntry]:
        return [*self._persistent, *self._session]

    def check(self, tool: str, arguments: dict) -> AllowlistEntry | None:
        for entry in self.entries():
            if entry.matches(tool, arguments):
                return entry
        return None

    def add(self, tool: str, pattern: str = "*", scope: str = "always") -> None:
        """Add an entry (deduped); persistent entries are saved."""
        entry = AllowlistEntry(tool, pattern, scope)
        target = self._persistent if scope == "always" else self._session
        for existing in target:
            if existing.tool == entry.tool and existing.pattern == entry.pattern:
                return  # already there
        target.append(entry)
        if scope == "always":
            self.save()

    def remove(self, tool: str, pattern: str = "*") -> bool:
        """Remove from both scopes; returns True when something was removed."""
        before = len(self._persistent) + len(self._session)
        self._persistent = [
            e for e in self._persistent
            if not (e.tool == tool and e.pattern == pattern)
        ]
        self._session = [
            e for e in self._session
            if not (e.tool == tool and e.pattern == pattern)
        ]
        removed = len(self._persistent) + len(self._session) != before
        if removed:
            self.save()
        return removed

    # ------------------------------------------------------------ P0.20

    def import_from_history(self, approvals: list[tuple[str, str]],
                            scope: str = "session") -> int:
        """Import repeated approvals as allowlist entries (session scope).

        ``approvals`` is a list of (tool, pattern) pairs collected from
        permission prompts. Returns the number of new entries.
        """
        added = 0
        for tool, pattern in approvals:
            entry = AllowlistEntry(tool, pattern, scope)
            target = self._persistent if scope == "always" else self._session
            if any(e.tool == entry.tool and e.pattern == entry.pattern
                   for e in target):
                continue
            target.append(entry)
            added += 1
        if scope == "always":
            self.save()
        return added

    def suggest_candidate(self, tool: str, arguments: dict,
                          approval_count: int, threshold: int = 3) -> str | None:
        """P0.9: after *threshold* approvals of the same pattern, propose
        the allowlist pattern for the call (None below threshold)."""
        if approval_count < threshold:
            return None
        pattern = suggest_pattern(tool, arguments)
        if self.check(tool, arguments) is not None:
            return None  # already allowed
        return pattern
