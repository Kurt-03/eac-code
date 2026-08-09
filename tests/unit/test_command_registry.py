"""Tests for the command registry (Phase F.1) and registry-driven dispatch."""


from eaccode.ui.command_def import (
    COMMAND_REGISTRY,
    all_command_names,
    get_command,
    help_text,
)
from eaccode.ui.commands import DISPATCH_TABLE, handle_command


class FakeApp:
    """Minimal stand-in for the REPL app."""

    def __init__(self):
        self.messages = []
        self._last_prompt = ""
        self._model_name = ""
        self._mode_name = ""
        self._show_reasoning = False
        self.verbose_level = "new"
        self.workdir = None
        self._total_usage = None
        self.memory_facts = []
        self.memory_store = None
        self._session_touched = set()
        self.loaded_skills = []

    def _switch_model(self, name):
        return f"Switching model to '{name}'..."

    def _retry_last(self):
        return "Retrying..."

    def action_copy_last(self):
        return None

    @staticmethod
    def project_hash(workdir):
        return "testhash"


def test_registry_covers_all_dispatchable_commands():
    """Every handler in DISPATCH_TABLE must have a registry entry."""
    for name in DISPATCH_TABLE:
        assert get_command(name) is not None, f"registry missing /{name}"
    # And every registry entry with a handler must be dispatchable.
    for cmd in COMMAND_REGISTRY:
        assert cmd.name in DISPATCH_TABLE, f"no handler for /{cmd.name}"


def test_registry_entries_have_help_text_and_category():
    for cmd in COMMAND_REGISTRY:
        assert cmd.description, cmd.name
        assert cmd.category in {"Session", "Configuration", "Tools & Skills", "Info", "Exit"}


def test_registry_aliases_resolve():
    assert get_command("/quit").name == "exit"
    assert get_command("?") is not None
    assert get_command("/exit").name == "exit"
    assert get_command("nonexistent") is None


def test_all_command_names_includes_aliases():
    names = all_command_names()
    assert "/exit" in names and "/quit" in names and "/help" in names


def test_help_text_grouped_by_category():
    text = help_text()
    assert "Session:" in text
    assert "Configuration:" in text
    assert "Tools & Skills:" in text
    assert "/undo" in text
    assert "/exit" in text


def test_handle_unknown_command():
    result = handle_command("/foobar", FakeApp())
    assert "Unknown command" in result.message


def test_handle_plain_text_is_noop():
    result = handle_command("Refactor auth.py", FakeApp())
    assert result.message is None
    assert result.should_exit is False


def test_status_command_shows_workdir():
    app = FakeApp()
    app.workdir = "/tmp/proj"
    result = handle_command("/status", app)
    assert "Workdir: /tmp/proj" in result.message


def test_cost_reset_zeros_usage():
    from eaccode.llm.client import TokenUsage

    app = FakeApp()
    app._total_usage = TokenUsage(input_tokens=10, output_tokens=5, cost_usd=0.01)
    app.last_usage = app._total_usage
    result = handle_command("/cost reset", app)
    assert "reset" in result.message.lower()
    assert app._total_usage.input_tokens == 0
    assert app._total_usage.output_tokens == 0


def test_compress_reduces_messages():
    from eaccode.llm.models import Message

    app = FakeApp()
    app.messages = [Message.user(f"msg {i}") for i in range(12)]
    result = handle_command("/compress", app)
    assert "Compressed" in result.message
    assert len(app.messages) < 12


def test_diff_command_invalid_mode():
    result = handle_command("/diff bogus", FakeApp())
    assert "Usage: /diff" in result.message


def test_skills_lists_loaded():
    app = FakeApp()
    app.loaded_skills = ["eaccode-development", "plan"]
    result = handle_command("/skills", app)
    assert "eaccode-development" in result.message
    assert "plan" in result.message
