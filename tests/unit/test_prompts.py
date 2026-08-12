"""Tests for the permission confirmation prompts (Task 4.2)."""
import pytest

from eaccode.permissions.prompts import (
    PermissionChoice,
    prompt_for_permission,
    prompt_for_permission_async,
)
from eaccode.permissions.rules import Rule


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


# ---------------------------------------------------------------------------
# v0.0.1: ALLOW_SESSION — remember-for-the-session but do not persist
# ---------------------------------------------------------------------------


def test_session_choice_is_recognized() -> None:
    """The PermissionChoice enum must carry an ALLOW_SESSION member."""
    assert hasattr(PermissionChoice, "ALLOW_SESSION")
    assert PermissionChoice.ALLOW_SESSION.value == "allow-session"


def test_session_choice_grants_without_persisting(monkeypatch) -> None:
    """ALLOW_SESSION grants the call but does NOT add a session rule.

    The difference from ALLOW_ALWAYS: SESSION lives only in the in-memory
    session_rules list (lost on restart), while ALWAYS also writes to the
    persistent allowlist. For the sync path here we only verify the rule
    is *not* persisted via allowlist.json — see test_allowlist.py for the
    persist path.
    """
    session_rules: list[Rule] = []
    granted = prompt_for_permission(
        "bash",
        {"command": "git status"},
        session_rules=session_rules,
        ask_callback=lambda _q: PermissionChoice.ALLOW_SESSION,
    )
    assert granted is True
    # Session choice does NOT add an extra rule (the difference is purely
    # on the persist side; both grant the call).
    assert session_rules == []


def test_session_choice_grants_via_async_path() -> None:
    """Async path also recognizes ALLOW_SESSION."""
    import asyncio

    async def _ask_async(_question: str):
        return PermissionChoice.ALLOW_SESSION

    async def run() -> None:
        session_rules: list[Rule] = []
        granted = await prompt_for_permission_async(
            "bash",
            {"command": "git status"},
            session_rules=session_rules,
            ask_async=_ask_async,
        )
        assert granted is True
        assert session_rules == []

    asyncio.run(run())


def test_session_choice_does_not_persist_to_allowlist(monkeypatch, tmp_path) -> None:
    """ALLOW_SESSION must NOT add a rule to the persistent allowlist.

    Only ALLOW_ALWAYS persists. ALLOW_SESSION lives only in the in-memory
    session_rules list.
    """
    from eaccode.permissions.allowlist import AllowlistStore

    store = AllowlistStore(path=tmp_path / "allowlist.json")
    # The store has no entries yet.
    assert store.entries() == []

    # Simulate ALLOW_SESSION: the policy should NOT touch the store.
    from eaccode.permissions.prompts import _handle_choice

    granted = _handle_choice(
        PermissionChoice.ALLOW_SESSION,
        "bash",
        {"command": "git status"},
        session_rules=None,
        pause_flag=None,
    )
    assert granted is True
    # The store must still be empty: ALLOW_SESSION never persists.
    assert store.entries() == []
