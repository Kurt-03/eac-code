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
        lines = [_strip_text(line) for line in log.lines]
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
        lines = [_strip_text(line) for line in log.lines]
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
        lines = [_strip_text(line) for line in app.query_one(RichLog).lines]
        # Phase H.6: friendly verb label — "⎿ Reading x.py" (fallback to the
        # raw expression only for unknown tools).
        assert any("⎿ Reading x.py" in line for line in lines)  # tool call line
        assert any("✓ read" in line for line in lines)  # tool result
        # v0.0.1: stream fragments are written live to the transcript.
        # The text may be split across multiple lines (one per delta),
        # so we check the joined text.
        joined = "".join(lines)
        assert "Hello" in joined and "world" in joined, (
            f"expected streamed text in transcript, got: {joined!r}"
        )


@pytest.mark.asyncio
async def test_repl_verbose_off_hides_successful_tools(repl_app, tmp_path):
    """/verbose off → only failed tool calls are shown."""
    from eaccode.agent.loop import AgentResult
    from eaccode.llm.client import TokenUsage
    from eaccode.llm.models import ToolCall
    from eaccode.tools.base import ToolResult

    class FakeAgent:
        async def run_streaming(self, history, **kwargs):
            on_text = kwargs.get("on_text_delta")
            if on_text:
                on_text("done")
            kwargs["on_tool_call"](ToolCall(id="1", name="read", arguments={"path": "x.py"}))
            kwargs["on_tool_result"](
                ToolCall(id="1", name="read", arguments={"path": "x.py"}),
                ToolResult(content="1 line"),
            )
            return AgentResult(
                final_text="done", messages=[], usage=TokenUsage(), turns=1, cost_usd=0.0
            )

    app = repl_app(workdir=tmp_path)
    async with app.run_test() as pilot:
        app._agent = FakeAgent()
        app._no_providers = False
        app.verbose_level = "off"
        inp = app.query_one(Input)
        inp.value = "go"
        await pilot.press("enter")
        lines = [_strip_text(line) for line in app.query_one(RichLog).lines]
        assert not any("⎿" in line for line in lines)  # start hidden
        assert not any("✓ read" in line for line in lines)  # result hidden
        joined = "".join(lines)
        assert "done" in joined  # final answer still there (streamed live)


def test_run_repl_passes_initial_messages(tmp_path, monkeypatch):
    """--continue hands the loaded session into the app (Phase B.5)."""
    from eaccode.ui.repl import run_repl

    captured = {}

    def fake_run(self):
        captured["messages"] = self.messages
        captured["workdir"] = self.workdir

    monkeypatch.setattr(EaccodeApp, "run", fake_run)
    run_repl(workdir=tmp_path, initial_messages=[{"role": "user", "content": "hi"}])
    assert captured["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["workdir"] == tmp_path.resolve()
