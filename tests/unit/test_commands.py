"""Tests for slash-command handling (Task 7.2)."""
import pytest

from eaccode.ui.commands import handle_command


class FakeApp:
    def __init__(self):
        self.messages = []
        self.policy_mode = "default"
        self.remembered = None

    @property
    def policy(self):
        class P:
            mode = "default"

            def __init__(self, parent):
                self._parent = parent

            @property
            def mode(self):
                return self._parent.policy_mode

            @mode.setter
            def mode(self, value):
                self._parent.policy_mode = value

        return P(self)


def test_help_command():
    result = handle_command("/help", FakeApp())
    assert result.should_exit is False
    assert "/mode" in result.message


def test_exit_command():
    result = handle_command("/exit", FakeApp())
    assert result.should_exit is True


def test_quit_alias():
    assert handle_command("/quit", FakeApp()).should_exit is True


def test_mode_switch():
    app = FakeApp()
    result = handle_command("/mode acceptEdits", app)
    assert result.message is not None
    assert app.policy_mode == "acceptEdits"


def test_mode_invalid():
    app = FakeApp()
    result = handle_command("/mode gibtsnicht", app)
    assert "Unknown mode" in result.message
    assert app.policy_mode == "default"


def test_unknown_command():
    result = handle_command("/foobar", FakeApp())
    assert "Unknown command" in result.message


def test_plain_text_is_not_a_command():
    result = handle_command("Refactor auth.py", FakeApp())
    assert result.message is None  # wird an den Agenten geschickt
