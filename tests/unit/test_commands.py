"""Tests for slash-command handling (Task 7.2)."""

from eaccode.ui.commands import handle_command


class _Policy:
    """Mirror of the real policy engine's mode surface."""

    def __init__(self, parent):
        self._parent = parent

    @property
    def mode(self):
        return self._parent.policy_mode

    @mode.setter
    def mode(self, value):
        self._parent.policy_mode = value


class FakeApp:
    def __init__(self, agent: bool = True):
        self.messages = []
        self.policy_mode = "default"
        self.remembered = None
        # A1 (audit): policy lives on the agent, not the App.
        self._agent = _Agent(self) if agent else None
        self._mode_name = None
        self._status_refreshes = 0

    def _refresh_status_rule(self):
        self._status_refreshes += 1


class _Agent:
    def __init__(self, parent):
        self.policy = _Policy(parent)


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
    assert app._mode_name == "acceptEdits"
    assert app._status_refreshes == 1


def test_mode_without_agent_is_guarded():
    """A1 (audit): /mode must not crash when the agent is not built yet."""
    app = FakeApp(agent=False)
    result = handle_command("/mode safeAuto", app)
    assert "not initialized" in result.message
    assert app.policy_mode == "default"


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
