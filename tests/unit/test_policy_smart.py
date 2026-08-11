"""Tests for safeAuto approval mode (Phase B.3, formerly A.5/smart).

The mode was renamed from `smart` to `safeAuto` (B.3): bash is
classified by key patterns first, then by the auxiliary LLM, and
fails open to ASK when no classifier is available.
"""
import pytest

from eaccode.config.settings import PermissionMode
from eaccode.permissions.policy import Action, PolicyEngine
from eaccode.permissions.rules import RuleSet


@pytest.fixture
def safe_auto():
    return PolicyEngine(PermissionMode.SAFE_AUTO, RuleSet())


def test_safe_auto_asks_on_dangerous_bash(safe_auto):
    # Key-pattern hit (recursive forced delete) → ASK without any LLM.
    d = safe_auto.decide("bash", {"command": "rm -rf /tmp/x"})
    assert d.action == Action.ASK


def test_safe_auto_asks_without_classifier(safe_auto, monkeypatch):
    # No provider/classifier → fail-open to ASK (never silent allow).
    monkeypatch.setattr(
        "eaccode.llm.aux_classifier.classify_command", lambda cmd: None
    )
    d = safe_auto.decide("bash", {"command": "git status"})
    assert d.action == Action.ASK


def test_safe_auto_approves_classified_safe_bash(safe_auto, monkeypatch):
    monkeypatch.setattr(
        "eaccode.llm.aux_classifier.classify_command", lambda cmd: "safe"
    )
    d = safe_auto.decide("bash", {"command": "git status"})
    assert d.action == Action.ALLOW


def test_safe_auto_other_tools_behave_like_default(safe_auto):
    d = safe_auto.decide("write", {"path": "x.py"})
    assert d.action == Action.ASK  # write is gated in default mode too


def test_safe_auto_deny_rule_still_wins(safe_auto):
    from eaccode.permissions.rules import Action as RuleAction
    from eaccode.permissions.rules import Rule

    safe_auto.rules = RuleSet(
        (Rule("bash", RuleAction.DENY, "*"),)
    )
    d = safe_auto.decide("bash", {"command": "echo hi"})
    assert d.action == Action.DENY


def test_safe_auto_allow_rule_still_wins(safe_auto):
    from eaccode.permissions.rules import Action as RuleAction
    from eaccode.permissions.rules import Rule, RuleSet

    safe_auto.rules = RuleSet(
        (Rule("bash", RuleAction.ALLOW, "*"),)
    )
    d = safe_auto.decide("bash", {"command": "rm -rf /"})
    assert d.action == Action.ALLOW
