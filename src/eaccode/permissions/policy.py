"""Policy engine (Task 4.1) — 4 modes x rules decide allow/ask/deny.

P7/C.1 Decision table (priority top→bottom; first match wins):

  1. Explicit DENY rule                          → DENY
  2. Explicit ALLOW rule (mode ≠ BYPASS)          → ALLOW (overrides ASK/DENY mode)
  3. Session-rule (from (a) at an ASK prompt)     → ALLOW (this session only)
  4. Persistent allowlist match (always)          → ALLOW (yields to 1 only)
  5. Mode default:
     - BYPASS_PERMISSIONS  → ALLOW (everything)
     - SAFE_AUTO           → ALLOW (safe tools + bash pattern classifier),
                            ASK for unknown bash, ASK otherwise
     - ACCEPT_EDITS        → ALLOW (write/edit), ASK (bash), ALLOW (safe reads)
     - PLAN                → DENY (mutating), ALLOW (safe reads)
     - DEFAULT             → ASK (bash/write/edit), ALLOW (safe reads)

Tests: tests/unit/test_policy_matrix.py (one assertion per cell).
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
# E3/E4 (audit): read-only tools are never asked about — Claude Code and
# Hermes don't prompt for reads. "todo" was a tool name that does not
# exist (it is todo_write), so the agent got asked permission to write
# a todo list in default mode.
# P7/A.1: skill_view is also a name that does not exist (the closest
# tool is skill_list) — keep it out of the safe-list so we never claim
# to auto-allow a tool that the registry does not actually contain.
_SAFE_TOOLS = (
    "read", "glob", "grep", "search_files",
    "web_fetch", "web_extract", "web_search",
    "tool_search", "clarify",
    "memory_recall", "skill_list",
    "todo_write",
)

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
                 allowlist=None, session_rules=None) -> None:
        self.mode = mode
        self.rules = rules
        # P0.9: persistent allowlist consulted before the mode default.
        self.allowlist = allowlist
        # P7/A.3: session_rules = "always (this run only)" entries
        # created when the user picks (a) at an ASK prompt. Survive
        # until the session ends, but yield to explicit DENY rules and
        # to permanent allowlist entries.
        self.session_rules: list[Rule] = session_rules or []

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

        # P7/A.3: session-rules win over the mode default (the user
        # explicitly said "this session, allow this pattern").
        for rule in self.session_rules:
            if rule.matches(tool, arguments):
                return Decision(
                    Action.ALLOW,
                    "Allowed by session rule",
                    rule,
                )

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
