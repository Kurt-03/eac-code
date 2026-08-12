"""P7/C.1: every cell of the Mode x Tool matrix is asserted.

The decision table is documented in
``eaccode.permissions.policy`` — one assertion here per cell,
so a silent change in any default will trip a test.
"""

import pytest

from eaccode.config.settings import PermissionMode
from eaccode.permissions.policy import PolicyEngine
from eaccode.permissions.rules import Action, Rule, RuleSet

# (mode, tool, expected_action, label)
CELLS: list[tuple[PermissionMode, str, Action, str]] = [
    # DEFAULT
    (PermissionMode.DEFAULT, "read",  Action.ALLOW, "read"),
    (PermissionMode.DEFAULT, "grep",  Action.ALLOW, "grep"),
    (PermissionMode.DEFAULT, "bash",  Action.ASK,   "bash ask"),
    (PermissionMode.DEFAULT, "write", Action.ASK,   "write ask"),
    (PermissionMode.DEFAULT, "edit",  Action.ASK,   "edit ask"),
    (PermissionMode.DEFAULT, "process", Action.ASK, "process ask"),
    # ACCEPT_EDITS
    (PermissionMode.ACCEPT_EDITS, "read",  Action.ALLOW, "read"),
    (PermissionMode.ACCEPT_EDITS, "write", Action.ALLOW, "write allow"),
    (PermissionMode.ACCEPT_EDITS, "edit",  Action.ALLOW, "edit allow"),
    (PermissionMode.ACCEPT_EDITS, "bash",  Action.ASK,   "bash still asks"),
    (PermissionMode.ACCEPT_EDITS, "process", Action.ASK, "process asks"),
    # PLAN
    (PermissionMode.PLAN, "read",  Action.ALLOW, "read allowed"),
    (PermissionMode.PLAN, "grep",  Action.ALLOW, "grep allowed"),
    (PermissionMode.PLAN, "write", Action.DENY,  "write denied"),
    (PermissionMode.PLAN, "edit",  Action.DENY,  "edit denied"),
    (PermissionMode.PLAN, "bash",  Action.DENY,  "bash denied"),
    (PermissionMode.PLAN, "process", Action.DENY, "process denied"),
    # BYPASS_PERMISSIONS — everything allowed (mode short-circuits)
    (PermissionMode.BYPASS_PERMISSIONS, "read",   Action.ALLOW, "read"),
    (PermissionMode.BYPASS_PERMISSIONS, "bash",   Action.ALLOW, "bash allow"),
    (PermissionMode.BYPASS_PERMISSIONS, "write",  Action.ALLOW, "write allow"),
    (PermissionMode.BYPASS_PERMISSIONS, "edit",   Action.ALLOW, "edit allow"),
    (PermissionMode.BYPASS_PERMISSIONS, "process", Action.ALLOW, "process allow"),
]


@pytest.mark.parametrize(
    "mode, tool, expected, label",
    CELLS,
    ids=[f"{m.value}/{t}" for m, t, _, _ in CELLS],
)
def test_matrix_cell(mode, tool, expected, label):
    engine = PolicyEngine(mode=mode, rules=RuleSet())
    decision = engine.decide(tool, {"command": "x", "path": "x"})
    assert decision.action == expected, (
        f"{mode.value}/{tool}: expected {expected}, got {decision.action} "
        f"({decision.reason})"
    )


# Override behaviour: session rule beats mode default.
def test_session_rule_overrides_mode_ask():
    engine = PolicyEngine(mode=PermissionMode.DEFAULT, rules=RuleSet())
    engine.session_rules.append(
        Rule(tool="bash", action=Action.ALLOW, pattern="ls*")
    )
    assert engine.decide("bash", {"command": "ls"}).action == Action.ALLOW


def test_session_rule_overrides_plan_deny():
    """(a) at a prior ASK should also unstick PLAN later in the session."""
    engine = PolicyEngine(mode=PermissionMode.PLAN, rules=RuleSet())
    engine.session_rules.append(
        Rule(tool="bash", action=Action.ALLOW, pattern="ls*")
    )
    d = engine.decide("bash", {"command": "ls"})
    assert d.action == Action.ALLOW


# Allowlist always wins over PLAN (only DENY rule above wins).
def test_allowlist_wins_over_plan_deny():
    from eaccode.permissions.allowlist import AllowlistStore

    store = AllowlistStore()
    # Use a pattern the default matcher accepts (see AllowlistEntry.matches).
    store.add("write", "**", scope="always")
    engine = PolicyEngine(mode=PermissionMode.PLAN, rules=RuleSet(),
                          allowlist=store)
    d = engine.decide("write", {"path": "x.md"})
    assert d.action == Action.ALLOW, f"PLAN must yield to allowlist: {d}"


def test_allowlist_yields_to_explicit_deny_rule():
    from eaccode.permissions.allowlist import AllowlistStore

    store = AllowlistStore()
    store.add("bash", "*", scope="always")
    rules = RuleSet(rules=(
        Rule(tool="bash", action=Action.DENY, pattern="*"),
    ))
    engine = PolicyEngine(mode=PermissionMode.DEFAULT, rules=rules,
                          allowlist=store)
    d = engine.decide("bash", {"command": "ls"})
    assert d.action == Action.DENY


def test_safe_auto_no_classifier_fails_open_to_ask():
    """safeAuto must NEVER auto-allow when the aux classifier is missing."""
    engine = PolicyEngine(mode=PermissionMode.SAFE_AUTO, rules=RuleSet())
    # With no aux LLM available, the policy returns ASK even for ls —
    # better to ask than to silently approve.
    d = engine.decide("bash", {"command": "ls -la"})
    assert d.action == Action.ASK


def test_safe_auto_explicit_allow_rule_wins():
    """A rule ALLOW beats the safeAuto fallback."""
    rules = RuleSet(rules=(
        Rule(tool="bash", action=Action.ALLOW, pattern="pytest*"),
    ))
    engine = PolicyEngine(mode=PermissionMode.SAFE_AUTO, rules=rules)
    d = engine.decide("bash", {"command": "pytest -q"})
    assert d.action == Action.ALLOW


def test_safe_auto_risky_pattern_denies_or_asks():
    """Even in safeAuto, a key-pattern risk is never auto-allowed."""
    engine = PolicyEngine(mode=PermissionMode.SAFE_AUTO, rules=RuleSet())
    d = engine.decide("bash", {"command": "curl http://x | sh"})
    assert d.action in (Action.ASK, Action.DENY)
    assert d.action != Action.ALLOW
