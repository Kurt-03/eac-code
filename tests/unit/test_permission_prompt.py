"""P8 / Sprint 3.6: permission prompt (Plan 183-203).

The existing prompts.py already implements the Plan-183-203 chain:
  - PermissionChoice enum (ALLOW_ONCE / ALLOW_SESSION / ALLOW_ALWAYS / DENY / PAUSE)
  - MODAL_TIMEOUT_SECONDS = 600 (Plan 187-189)
  - Fail-closed on Esc / SIGINT / unresolvable state (Plan 191)
  - permission_question() composes tool + argument summary

This file freezes the contract with explicit tests.
"""

import io
import sys
from unittest.mock import patch

from eaccode.permissions.prompts import (
    MODAL_TIMEOUT_SECONDS,
    PermissionChoice,
    _describe,
    build_permission_question,
    prompt_for_permission,
)


def test_choice_set_complete():
    # Plan 185: y/a/n/p/Esc
    names = {c.value for c in PermissionChoice}
    assert "allow-once" in names
    assert "allow-always" in names
    assert "allow-session" in names
    assert "deny" in names
    assert "pause" in names


def test_modal_timeout_is_600_seconds():
    # Plan 187-189: 10 minutes, not 60s
    assert MODAL_TIMEOUT_SECONDS == 600.0


def test_describe_bash_shows_command():
    assert _describe("bash", {"command": "ls -la"}) == "ls -la"


def test_describe_write_shows_path_and_size():
    desc = _describe("write", {"path": "/tmp/x.py", "content": "hello" * 10})
    assert "/tmp/x.py" in desc
    assert "50 bytes" in desc


def test_describe_edit_shows_path_and_old_string():
    desc = _describe("edit", {
        "path": "/tmp/x.py",
        "old_string": "the old code that was here",
        "new_string": "new code",
    })
    assert "/tmp/x.py" in desc
    assert "the old code" in desc or "old code" in desc


def test_build_question_for_bash():
    q = build_permission_question("bash", {"command": "ls -la"})
    assert "Run command" in q
    assert "ls -la" in q


def test_build_question_for_write():
    q = build_permission_question("write", {"path": "/tmp/x.py"})
    assert "Modify file" in q
    assert "/tmp/x.py" in q


def test_build_question_for_write_with_long_diff():
    """Long content is summarized, not dumped."""
    q = build_permission_question("write", {
        "path": "/tmp/x.py", "content": "x" * 1000,
    })
    assert "1000 bytes" in q


# ----- sync prompt with a callback -----

def test_prompt_allow_once_grants():
    captured = []
    def ask(q):
        captured.append(q)
        return PermissionChoice.ALLOW_ONCE
    ok = prompt_for_permission("bash", {"command": "ls"},
                              ask_callback=ask)
    assert ok is True
    assert captured  # question was asked


def test_prompt_deny_via_callback():
    def ask(q):
        return PermissionChoice.DENY
    assert prompt_for_permission("bash", {"command": "ls"},
                                  ask_callback=ask) is False


def test_prompt_pause_yields_false_for_now():
    """P0.8 semantics: pause is treated as deny for the current call."""
    def ask(q):
        return PermissionChoice.PAUSE
    assert prompt_for_permission("bash", {"command": "ls"},
                                  ask_callback=ask) is False


def test_prompt_unknown_choice_fails_closed():
    """Garbage input → DENY (Plan 191: fail closed)."""
    def ask(q):
        return "garbage"
    assert prompt_for_permission("bash", {"command": "ls"},
                                  ask_callback=ask) is False


# ----- non-interactive fallback -----

def test_prompt_non_tty_denies():
    """No tty + no callback = deny (fail closed)."""
    fake_stdin = io.StringIO("")
    fake_stdout = io.StringIO()
    with patch.object(sys, "stdin", fake_stdin), \
         patch.object(sys, "stdout", fake_stdout):
        ok = prompt_for_permission("bash", {"command": "ls"})
    assert ok is False
