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
    rules = RuleSet(rules=[Rule(tool="*", action=Action.ALLOW, pattern="*")])
    policy = PolicyEngine(mode=PermissionMode.DEFAULT, rules=rules)
    assert policy.decide("bash", {"command": "anything"}).action == Action.ALLOW
