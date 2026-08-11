"""Tests for J-phase features (J.2/J.6/J.31/J.34/J.44)."""

from eaccode.llm.client import TokenUsage
from eaccode.ui.commands import _cmd_cost, handle_command


class _FakeApp:
    def __init__(self):
        self.messages = []
        self._session_title = ""
        self._session_id = "abc123"
        self._usage_by_model = {}
        self._reasoning_text = ""


def test_fence_stats_counters():
    from eaccode.llm.stream_fence import fence_stats

    stats = fence_stats()
    assert set(stats) == {"claimed", "dropped"}
    assert stats["claimed"] >= 0


def test_clear_requires_confirm():
    result = handle_command("/clear", _FakeApp())
    assert "--yes" in result.message
    result = handle_command("/clear --yes", _FakeApp())
    assert "cleared" in result.message.lower()


def test_tips_returns_something():
    result = handle_command("/tips", _FakeApp())
    assert result.message


def test_debug_returns_stats():
    result = handle_command("/debug", _FakeApp())
    assert "Stream diagnostics" in result.message
    assert "claimed" in result.message


def test_cost_by_model():
    app = _FakeApp()
    usage = TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.01)
    app._usage_by_model["test-model"] = usage
    app.last_usage = None
    result = _cmd_cost(app, "")
    assert "test-model" in result.message
    assert "150 tok" in result.message


def test_cost_reset_clears_by_model():
    app = _FakeApp()
    app._usage_by_model["m"] = TokenUsage(input_tokens=1)
    _cmd_cost(app, "reset")
    assert app._usage_by_model == {}
