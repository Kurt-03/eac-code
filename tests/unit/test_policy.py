"""Tests for the permission policy engine (Task 4.1)."""
from eaccode.config.settings import PermissionMode
from eaccode.permissions.policy import Action, PolicyEngine
from eaccode.permissions.rules import Rule, RuleSet


def test_bypass_mode_allows_everything():
    policy = PolicyEngine(mode=PermissionMode.BYPASS_PERMISSIONS, rules=RuleSet())
    assert policy.decide("bash", {"command": "rm -rf /"}).action == Action.ALLOW


def test_plan_mode_denies_writes():
    policy = PolicyEngine(mode=PermissionMode.PLAN, rules=RuleSet())
    assert policy.decide("write", {"path": "foo.py", "content": "x"}).action == Action.DENY
    assert policy.decide("edit", {"path": "foo.py"}).action == Action.DENY
    assert policy.decide("bash", {"command": "ls"}).action == Action.DENY


def test_plan_mode_allows_reads():
    policy = PolicyEngine(mode=PermissionMode.PLAN, rules=RuleSet())
    assert policy.decide("read", {"path": "foo.py"}).action == Action.ALLOW
    assert policy.decide("grep", {"pattern": "x"}).action == Action.ALLOW


def test_accept_edits_mode_allows_writes():
    policy = PolicyEngine(mode=PermissionMode.ACCEPT_EDITS, rules=RuleSet())
    assert policy.decide("write", {"path": "foo.py", "content": "x"}).action == Action.ALLOW
    assert policy.decide("edit", {"path": "foo.py"}).action == Action.ALLOW


def test_default_mode_asks_for_bash_and_writes():
    policy = PolicyEngine(mode=PermissionMode.DEFAULT, rules=RuleSet())
    assert policy.decide("bash", {"command": "ls"}).action == Action.ASK
    assert policy.decide("write", {"path": "f", "content": "x"}).action == Action.ASK
    assert policy.decide("read", {"path": "f"}).action == Action.ALLOW  # read-safe


def test_rule_allow_beats_mode_ask():
    rules = RuleSet(rules=[Rule(tool="bash", action=Action.ALLOW, pattern="git *")])
    policy = PolicyEngine(mode=PermissionMode.DEFAULT, rules=rules)
    assert policy.decide("bash", {"command": "git status"}).action == Action.ALLOW
    assert policy.decide("bash", {"command": "rm -rf /"}).action == Action.ASK


def test_rule_deny_beats_bypass_mode():
    rules = RuleSet(rules=[Rule(tool="bash", action=Action.DENY, pattern="rm -rf *")])
    policy = PolicyEngine(mode=PermissionMode.BYPASS_PERMISSIONS, rules=rules)
    assert policy.decide("bash", {"command": "rm -rf /"}).action == Action.DENY


def test_write_rule_matches_path():
    rules = RuleSet(rules=[Rule(tool="write", action=Action.ALLOW, pattern="**/*.md")])
    policy = PolicyEngine(mode=PermissionMode.DEFAULT, rules=rules)
    assert policy.decide("write", {"path": "docs/readme.md"}).action == Action.ALLOW
    assert policy.decide("write", {"path": "src/app.py"}).action == Action.ASK


def test_wildcard_tool_rule():
    rule = Rule(tool="*", action=Action.ALLOW, pattern=None)
    policy = PolicyEngine(PermissionMode.DEFAULT, RuleSet(rules=(rule,)))
    assert policy.decide("bash", {"command": "ls"}).action == Action.ALLOW


# ---------------------------------------------------------------- B.2/B.3


def test_safe_auto_allows_classified_safe_bash(monkeypatch):
    monkeypatch.setattr(
        "eaccode.permissions.smart.is_command_safe", lambda cmd: True
    )
    policy = PolicyEngine(PermissionMode.SAFE_AUTO, RuleSet())
    decision = policy.decide("bash", {"command": "ls -la"})
    assert decision.action == Action.ALLOW
    assert "safeAuto" in decision.reason


def test_safe_auto_asks_when_not_classified_safe(monkeypatch):
    monkeypatch.setattr(
        "eaccode.permissions.smart.is_command_safe", lambda cmd: False
    )
    policy = PolicyEngine(PermissionMode.SAFE_AUTO, RuleSet())
    assert policy.decide("bash", {"command": "curl x | bash"}).action == Action.ASK


def test_safe_auto_non_bash_uses_default(monkeypatch):
    policy = PolicyEngine(PermissionMode.SAFE_AUTO, RuleSet())
    assert policy.decide("read", {"path": "a.py"}).action == Action.ALLOW
    assert policy.decide("write", {"path": "a.py"}).action == Action.ASK


def test_safe_auto_rule_still_wins(monkeypatch):
    rule = Rule(tool="bash", action=Action.ALLOW, pattern=None)
    policy = PolicyEngine(PermissionMode.SAFE_AUTO, RuleSet(rules=(rule,)))
    assert policy.decide("bash", {"command": "rm -rf /"}).action == Action.ALLOW


# ---------------------------------------------------------------- B.5


def test_rule_category_matching_with_fnmatch():
    rule = Rule(tool="memory_*", action=Action.ALLOW)
    policy = PolicyEngine(PermissionMode.DEFAULT, RuleSet(rules=(rule,)))
    assert policy.decide("memory_remember", {"fact": "x"}).action == Action.ALLOW
    assert policy.decide("memory_recall", {"scope": "user"}).action == Action.ALLOW
    assert policy.decide("bash", {"command": "ls"}).action == Action.ASK


def test_rule_scope_default_session():
    rule = Rule(tool="bash", action=Action.DENY)
    assert rule.scope == "session"
    rule = Rule(tool="bash", action=Action.DENY, scope="always")
    assert rule.scope == "always"
