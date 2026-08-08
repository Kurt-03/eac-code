"""Tests for smart approval mode (Phase A.5)."""
import pytest

from eaccode.config.settings import PermissionMode
from eaccode.permissions.policy import Action, PolicyEngine
from eaccode.permissions.rules import RuleSet


@pytest.fixture
def smart():
    return PolicyEngine(PermissionMode.SMART, RuleSet())


def test_smart_auto_approves_safe_bash(smart):
    d = smart.decide("bash", {"command": "git status"})
    assert d.action == Action.ALLOW


def test_smart_asks_on_dangerous_bash(smart):
    d = smart.decide("bash", {"command": "rm -rf /tmp/x"})
    assert d.action == Action.ASK


def test_smart_other_tools_behave_like_default(smart):
    d = smart.decide("write", {"path": "x.py"})
    assert d.action == Action.ASK  # write is gated in default mode too


def test_smart_deny_rule_still_wins(smart):
    from eaccode.permissions.rules import Action as RuleAction
    from eaccode.permissions.rules import Rule

    smart.rules = RuleSet(
        (Rule("bash", RuleAction.DENY, "*"),)
    )
    d = smart.decide("bash", {"command": "echo hi"})
    assert d.action == Action.DENY


def test_smart_allow_rule_still_wins(smart):
    from eaccode.permissions.rules import Action as RuleAction
    from eaccode.permissions.rules import Rule, RuleSet

    smart.rules = RuleSet(
        (Rule("bash", RuleAction.ALLOW, "*"),)
    )
    d = smart.decide("bash", {"command": "rm -rf /"})
    assert d.action == Action.ALLOW
