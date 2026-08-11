"""Policy engine (Task 4.1) — 4 modes x rules decide allow/ask/deny.

Priority: explicit DENY rules win over everything, then ALLOW rules,
then the mode default.
"""
from __future__ import annotations

from dataclasses import dataclass

from eaccode.config.settings import PermissionMode
from eaccode.permissions.rules import Action, Rule, RuleSet


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str
    matched_rule: Rule | None = None


# Per-mode defaults: which tools ask, which are safe
_SAFE_TOOLS = ("read", "glob", "grep", "web_fetch", "web_search", "todo", "session_search")

_MODE_DEFAULTS: dict[PermissionMode, dict[str, Action]] = {
    PermissionMode.DEFAULT: {
        **{t: Action.ALLOW for t in _SAFE_TOOLS},
        "bash": Action.ASK,
        "write": Action.ASK,
        "edit": Action.ASK,
        "_default": Action.ASK,
    },
    PermissionMode.ACCEPT_EDITS: {
        **{t: Action.ALLOW for t in _SAFE_TOOLS},
        "write": Action.ALLOW,
        "edit": Action.ALLOW,
        "bash": Action.ASK,
        "_default": Action.ASK,
    },
    PermissionMode.PLAN: {
        **{t: Action.ALLOW for t in _SAFE_TOOLS},
        "bash": Action.DENY,
        "write": Action.DENY,
        "edit": Action.DENY,
        "_default": Action.DENY,
    },
    PermissionMode.BYPASS_PERMISSIONS: {},  # special-cased: everything allowed
}


class PolicyEngine:
    def __init__(self, mode: PermissionMode, rules: RuleSet,
                 allowlist=None) -> None:
        self.mode = mode
        self.rules = rules
        # P0.9: persistent allowlist consulted before the mode default.
        self.allowlist = allowlist

    def decide(self, tool: str, arguments: dict) -> Decision:
        deny_rule: Rule | None = None
        allow_rule: Rule | None = None
        for rule in self.rules.rules:
            if rule.matches(tool, arguments):
                if rule.action == Action.DENY:
                    deny_rule = rule
                    break
                if rule.action == Action.ALLOW and allow_rule is None:
                    allow_rule = rule

        if deny_rule:
            return Decision(Action.DENY, f"Denied by rule: {deny_rule}", deny_rule)

        # P0.9: an explicit allowlist entry wins over the mode default
        # (an "always" the user chose once must survive PLAN mode), but
        # explicit DENY rules above still win.
        if self.allowlist is not None:
            entry = self.allowlist.check(tool, arguments)
            if entry is not None:
                return Decision(
                    Action.ALLOW,
                    f"Allowed by allowlist ({entry.scope})",
                    None,
                )

        if self.mode == PermissionMode.BYPASS_PERMISSIONS:
            reason = (
                "Allowed by rule + bypass mode"
                if allow_rule
                else "Bypass permissions mode"
            )
            return Decision(Action.ALLOW, reason, allow_rule)

        if self.mode == PermissionMode.SAFE_AUTO:
            return self._decide_safe_auto(tool, arguments, allow_rule)

        default_action = _MODE_DEFAULTS[self.mode].get(
            tool, _MODE_DEFAULTS[self.mode]["_default"]
        )
        if allow_rule and default_action in (Action.ASK, Action.DENY):
            return Decision(Action.ALLOW, "Allowed by rule", allow_rule)
        return Decision(
            default_action,
            f"Default action for {self.mode.value} mode on {tool}",
        )

    def _decide_safe_auto(
        self, tool: str, arguments: dict, allow_rule: Rule | None
    ) -> Decision:
        """safeAuto (B.2/B.3): bash is classified — key patterns first,
        then the aux LLM; unknown/unavailable fails open to ASK."""
        if allow_rule:
            return Decision(Action.ALLOW, "Allowed by rule", allow_rule)
        if tool == "bash":
            from eaccode.permissions.smart import is_command_safe

            command = str(arguments.get("command", ""))
            if is_command_safe(command):
                return Decision(
                    Action.ALLOW,
                    "safeAuto: classified safe",
                )
            return Decision(
                Action.ASK,
                "safeAuto: not classified safe — confirm?",
            )
        default_action = _MODE_DEFAULTS[PermissionMode.DEFAULT].get(
            tool, _MODE_DEFAULTS[PermissionMode.DEFAULT]["_default"]
        )
        return Decision(default_action, f"safeAuto default for {tool}")
