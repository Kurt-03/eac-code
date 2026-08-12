"""P7/A.3: session_rules survive a 'a' choice and stop re-asking."""

from eaccode.config.settings import PermissionMode
from eaccode.permissions.policy import PolicyEngine
from eaccode.permissions.rules import Action, Rule, RuleSet


def test_session_rule_matches_after_a_choice():
    # Simulate the user choosing (a) on a bash ls call.
    engine = PolicyEngine(mode=PermissionMode.DEFAULT, rules=RuleSet())
    first = engine.decide("bash", {"command": "ls -la"})
    assert first.action.value == "ask"

    # Record the same 'always' the prompts._remember_rule() does.
    head = "ls"
    engine.session_rules.append(
        Rule(tool="bash", action=Action.ALLOW, pattern=f"{head} *")
    )

    # Same command again — no prompt.
    second = engine.decide("bash", {"command": "ls -la"})
    assert second.action.value == "allow"
    assert "session rule" in second.reason


def test_session_rule_only_matches_similar_command():
    engine = PolicyEngine(mode=PermissionMode.DEFAULT, rules=RuleSet())
    engine.session_rules.append(
        Rule(tool="bash", action=Action.ALLOW, pattern="ls *")
    )

    # Different command family — must still ask.
    d = engine.decide("bash", {"command": "rm -rf /tmp/x"})
    assert d.action.value == "ask"


def test_session_rule_yields_to_explicit_deny():
    """The user's session 'always' must not override a hard deny."""
    rules = RuleSet(rules=(
        Rule(tool="bash", action=Action.DENY, pattern="*"),
    ))
    engine = PolicyEngine(mode=PermissionMode.DEFAULT, rules=rules)
    engine.session_rules.append(
        Rule(tool="bash", action=Action.ALLOW, pattern="ls *")
    )
    d = engine.decide("bash", {"command": "ls"})
    assert d.action.value == "deny"


def test_default_constructor_has_empty_session_rules():
    engine = PolicyEngine(mode=PermissionMode.DEFAULT, rules=RuleSet())
    assert engine.session_rules == []


def test_existing_constructor_kwargs_still_work():
    """Existing PolicyEngine users (allowlist, mode, rules) keep working."""
    engine = PolicyEngine(
        mode=PermissionMode.PLAN,
        rules=RuleSet(),
        allowlist=None,
    )
    assert engine.mode == PermissionMode.PLAN
    assert engine.allowlist is None
    assert engine.session_rules == []
