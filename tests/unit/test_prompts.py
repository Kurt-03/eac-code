"""Tests for the permission confirmation prompts (Task 4.2)."""
import pytest
from click.testing import CliRunner

from eaccode.permissions.prompts import prompt_for_permission
from eaccode.permissions.rules import Action, Rule


@pytest.mark.parametrize("answer,expected", [("y", True), ("n", False)])
def test_prompt_yes_no(answer, expected, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)  # interactive
    monkeypatch.setattr("click.confirm", lambda *a, **k: answer == "y")
    assert prompt_for_permission("bash", {"command": "ls"}) is expected


def test_prompt_always_allow_adds_session_rule(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("click.confirm", lambda *a, **k: True)
    session_rules: list[Rule] = []
    granted = prompt_for_permission(
        "bash", {"command": "git status"}, session_rules=session_rules
    )
    assert granted is True
    assert session_rules  # "always allow" record created


def test_prompt_no_rule_without_always(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("click.confirm", lambda *a, **k: False)
    session_rules: list[Rule] = []
    granted = prompt_for_permission(
        "bash", {"command": "git status"}, session_rules=session_rules
    )
    assert granted is False
    assert session_rules == []  # no "always allow" on plain no


def test_non_interactive_defaults_to_deny(monkeypatch):
    """In non-TTY contexts (CI, pipes) the prompt must not hang — deny by default."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert prompt_for_permission("bash", {"command": "ls"}) is False
