"""Allow/Ask/Deny rules (Task 4.1) — fnmatch patterns over tool arguments.

B.5: rules carry a scope (``session`` = this process, ``always`` =
persisted like allowlist entries) and tool names support fnmatch
wildcards for category matching (e.g. ``memory_*``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatch


class Action(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class Rule:
    tool: str  # "bash", "write", "edit", "*", or a fnmatch pattern
    action: Action
    pattern: str | None = None  # fnmatch pattern on the relevant argument
    scope: str = "session"  # B.5: session | always

    def matches(self, tool: str, arguments: dict) -> bool:
        if not (self.tool == "*" or fnmatch(tool, self.tool)):
            return False
        if self.pattern is None:
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


@dataclass(frozen=True)
class RuleSet:
    rules: tuple[Rule, ...] = ()

    def find_match(self, tool: str, arguments: dict) -> Rule | None:
        for rule in self.rules:
            if rule.matches(tool, arguments):
                return rule
        return None
