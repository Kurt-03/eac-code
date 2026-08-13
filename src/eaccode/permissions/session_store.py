"""On-disk store for ephemeral session rules (Plan 204-215).

A ``session rule`` is a user-created grant or ban that survives a
REPL restart but is purged when the agent stops. It's the
"for this session" alternative to ``allowlist`` (which is permanent)
and ``user_deny`` (which is per-pipeline).

Storage layout::

    $EACCODE_CONFIG/session_rules.json
        [
          {"tool": "bash", "pattern": "ls *",     "action": "allow"},
          {"tool": "write", "pattern": "*.tmp",   "action": "deny"},
          ...
        ]

We use plain JSON (no orjson) for portability — the file is read at
start of every REPL session and written on every rule change.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from eaccode.permissions.rules import Action, Rule


@dataclass(frozen=True)
class SessionRule(Rule):
    """A rule tagged with the session-id; the dataclass adds the
    inherent Rule fields plus an ``id`` so we can remove it."""

    id: str | None = None  # uuid4 or None for legacy


def _to_session_rule(rule: Rule) -> SessionRule:
    return SessionRule(
        tool=rule.tool, action=rule.action, pattern=rule.pattern,
        scope=rule.scope, id=None,
    )


class SessionRuleStore:
    """Ephemeral rules stored in a single JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            from eaccode.config.paths import EaccodePaths
            path = EaccodePaths().config_dir / "session_rules.json"
        self.path = path
        self._rules: list[SessionRule] = []
        self.load()

    def rules(self) -> tuple[Rule, ...]:
        """All rules as the legacy Rule type so existing matchers work."""
        return tuple(_to_session_rule(r) for r in self._rules)

    def add(self, tool: str, pattern: str, action: Action) -> SessionRule:
        rule = SessionRule(
            tool=tool, action=action, pattern=pattern or None,
            scope="session", id=None,
        )
        self._rules.append(rule)
        self.save()
        return rule

    def remove(self, tool: str, pattern: str) -> bool:
        before = len(self._rules)
        self._rules = [
            r for r in self._rules
            if not (r.tool == tool and (r.pattern or "") == pattern)
        ]
        if len(self._rules) < before:
            self.save()
            return True
        return False

    def clear(self) -> None:
        self._rules = []
        self.save()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, list):
            return
        out: list[SessionRule] = []
        for e in raw:
            if not isinstance(e, dict):
                continue
            try:
                out.append(SessionRule(
                    tool=str(e["tool"]),
                    action=Action(str(e.get("action", Action.ALLOW))),
                    pattern=e.get("pattern"),
                    scope=str(e.get("scope", "session")),
                    id=e.get("id"),
                ))
            except (KeyError, ValueError):
                continue
        self._rules = out

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {**asdict(r), "id": r.id, "pattern": r.pattern,
             "action": r.action.value if isinstance(r.action, Action) else str(r.action)}
            for r in self._rules
        ]
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
