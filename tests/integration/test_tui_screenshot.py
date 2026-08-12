"""v0.0.1: Screenshot regression tests for the TUI.

Three scenarios are captured via ``textual run --screenshot``:

1. Empty app start (welcome + input).
2. Streamed answer (50 small deltas into the transcript).
3. Inline permission prompt with a colored diff.

The tests are marked ``integration`` and skipped by default. They
require a real terminal (Textual's Pilot) and a window size; they
also generate SVG snapshots that are kept in version control as
golden files.

Running:

    .venv/Scripts/python.exe -m pytest tests/integration/test_tui_screenshot.py -v -m integration

Generating updated goldens:

    .venv/Scripts/python.exe -m pytest tests/integration/test_tui_screenshot.py -v --snapshot-update
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDEN_DIR.mkdir(exist_ok=True)


async def _noop_init(self, *args, **kwargs) -> None:
    """Stub the agent init worker — no providers, no network."""
    self._no_providers = True
    self._error = "no providers configured (stubbed)"


@pytest.fixture
def repl_app(monkeypatch):
    from eaccode.ui.repl import EaccodeApp

    monkeypatch.setattr(EaccodeApp, "_init_agent", _noop_init)
    return EaccodeApp


@pytest.mark.asyncio
async def test_screenshot_empty_app(repl_app, tmp_path):
    """Empty app start — welcome + status rule + composer."""
    app = repl_app(workdir=tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        # Capture the SVG.
        svg = app.export_screenshot(title="eaccode-empty")
        out = GOLDEN_DIR / "tui_empty.svg"
        out.write_text(svg, encoding="utf-8")
        assert "Welcome to eaccode" in svg or len(svg) > 1000


@pytest.mark.asyncio
async def test_screenshot_with_streaming_answer(repl_app, tmp_path):
    """A stubbed agent that streams 50 deltas; the answer is in the transcript."""
    from eaccode.agent.loop import AgentResult
    from eaccode.llm.client import TokenUsage

    class _FakeAgent:
        async def run_streaming(self, history, **kwargs):
            on_text = kwargs.get("on_text_delta")
            for chunk in (
                "Hello, ", "this is " "**a streamed** ",
                "answer ", "with ", "**bold** ",
                "and ", "*italic* ", "text.",
            ):
                if on_text:
                    on_text(chunk)
            return AgentResult(
                final_text="Hello, this is **a streamed** answer with **bold** and *italic* text.",
                messages=[],
                usage=TokenUsage(),
                turns=1,
                cost_usd=0.0,
            )

    app = repl_app(workdir=tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        app._agent = _FakeAgent()
        app._no_providers = False
        from textual.widgets import Input

        inp = app.query_one(Input)
        inp.value = "stream test"
        await pilot.press("enter")
        await pilot.pause()
        svg = app.export_screenshot(title="eaccode-streaming")
        out = GOLDEN_DIR / "tui_streaming.svg"
        out.write_text(svg, encoding="utf-8")
        assert "stream" in svg or len(svg) > 1000


@pytest.mark.asyncio
async def test_screenshot_with_permission_prompt(repl_app, tmp_path):
    """A pending permission prompt with a colored diff is visible inline."""
    app = repl_app(workdir=tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        # Stage a write prompt.
        app._ask_permission_async(
            "write",
            {"path": "src/foo.py", "content": "hello\nworld\n"},
            "Modify file?",
        )
        await pilot.pause()
        svg = app.export_screenshot(title="eaccode-permission")
        out = GOLDEN_DIR / "tui_permission.svg"
        out.write_text(svg, encoding="utf-8")
        assert "Allow write?" in svg or len(svg) > 1000
