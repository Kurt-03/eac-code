"""Allow/Ask/Deny rules (Task 4.1) — fnmatch patterns over tool arguments."""
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
    tool: str  # "bash", "write", "edit", or "*"
    action: Action
    pattern: str | None = None  # fnmatch pattern on the relevant argument

    def matches(self, tool: str, arguments: dict) -> bool:
        if self.tool != "*" and self.tool != tool:
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
