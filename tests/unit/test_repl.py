"""Tests for the Textual REPL (Task 7.1/7.3) using Textual's Pilot.

Verifies the real event path: typing into the Input, submitting, slash
commands, and the streaming callback wiring — without network (the agent
init worker is stubbed).
"""
import pytest
from textual.widgets import Input, RichLog

from eaccode.ui.repl import EaccodeApp


def _strip_text(strip) -> str:
    return "".join(s.text for s in strip)


async def _noop_init(self, *args, **kwargs) -> None:
    """Stub the agent init worker — no providers, no network."""
    self._no_providers = True
    self._error = "no providers configured (stubbed)"


@pytest.fixture
def repl_app(monkeypatch):
    monkeypatch.setattr(EaccodeApp, "_init_agent", _noop_init)
    return EaccodeApp


@pytest.mark.asyncio
async def test_repl_submit_plain_message(repl_app, tmp_path):
    app = repl_app(workdir=tmp_path)
    async with app.run_test() as pilot:
        log = app.query_one(RichLog)
        inp = app.query_one(Input)
        inp.value = "hello there"
        await pilot.press("enter")
        lines = [_strip_text(l) for l in log.lines]
        assert any("hello there" in line for line in lines)  # user prompt shown
        assert any("stubbed" in line for line in lines)  # error message shown


@pytest.mark.asyncio
async def test_repl_slash_help(repl_app, tmp_path):
    app = repl_app(workdir=tmp_path)
    async with app.run_test() as pilot:
        log = app.query_one(RichLog)
        inp = app.query_one(Input)
        inp.value = "/help"
        await pilot.press("enter")
        lines = [_strip_text(l) for l in log.lines]
        assert any("Slash commands" in line for line in lines)
        assert any("/copy" in line for line in lines)


@pytest.mark.asyncio
async def test_repl_streaming_callbacks(repl_app, tmp_path):
    """A stubbed agent that emits deltas + tool calls → cards appear."""
    from eaccode.agent.loop import AgentResult
    from eaccode.llm.client import TokenUsage
    from eaccode.llm.models import ToolCall

    class FakeAgent:
        async def run_streaming(self, history, **kwargs):
            cb = kwargs.get("on_tool_call")
            cb(ToolCall(id="1", name="read", arguments={"path": "x.py"}))
            on_result = kwargs.get("on_tool_result")
            from eaccode.tools.base import ToolResult

            on_result(
                ToolCall(id="1", name="read", arguments={"path": "x.py"}),
                ToolResult(content="1 line"),
            )
            on_text = kwargs.get("on_text_delta")
            for chunk in ("Hello", " world"):
                on_text(chunk)
            return AgentResult(
                final_text="Hello world",
                messages=[],
                usage=TokenUsage(),
                turns=1,
                cost_usd=0.0,
            )

    app = repl_app(workdir=tmp_path)
    async with app.run_test() as pilot:
        app._agent = FakeAgent()
        app._no_providers = False
        inp = app.query_one(Input)
        inp.value = "read the file"
        await pilot.press("enter")
        lines = [_strip_text(l) for l in app.query_one(RichLog).lines]
        assert any("⚙ read" in line for line in lines)  # tool card
        assert any("✓ read" in line for line in lines)  # tool result
        assert any("Hello world" in line for line in lines)  # final answer
