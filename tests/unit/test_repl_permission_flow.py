"""Headless integration test: permission keys in the real Textual app.

Uses Textual's ``run_test`` + Pilot to drive the actual EaccodeApp:
a scripted agent requests a write, the inline permission prompt
appears, we press ``y``, and the file must be written and the input
restored. This is the regression test for the v0.4.0.x permission
focus bugs ("ich kann drücken was ich will, es passiert nix").

Note: the agent turn runs as a background task (as Textual does for
Event.Submitted handlers that await), so the Pilot can press keys
while the turn is parked on the permission future.
"""

import asyncio

import pytest


def _make_agent(tmp_path, ask_async):
    from eaccode.agent.loop import AgentConfig, AgentLoop
    from eaccode.config.settings import PermissionMode
    from eaccode.llm._stream import StreamUsage
    from eaccode.llm.models import ToolCall
    from eaccode.permissions.policy import PolicyEngine
    from eaccode.permissions.rules import RuleSet
    from eaccode.tools.factory import build_default_registry

    class ScriptedClient:
        calls = 0

        async def stream(self, req):
            self.calls += 1
            if self.calls == 1:
                yield ToolCall(
                    id="t1", name="write",
                    arguments={"path": "out.txt", "content": "permission-ok"},
                )
                yield StreamUsage(input_tokens=10, output_tokens=5, cost_usd=0.0)
            else:
                yield "Done."
                yield StreamUsage(input_tokens=20, output_tokens=10, cost_usd=0.0)

    client = ScriptedClient()
    registry = build_default_registry()
    policy = PolicyEngine(PermissionMode.DEFAULT, RuleSet())
    config = AgentConfig(workdir=tmp_path, max_turns=5)
    config.ask_async = ask_async
    return AgentLoop(client, registry, policy, config), client


async def _prepare_app(tmp_path, agent, app):
    """Mount the app without letting on_mount's worker build a real agent."""
    async def _noop_init_agent(*a, **k):
        pass

    app._init_agent = _noop_init_agent  # type: ignore[method-assign]
    app._agent = agent
    app._no_providers = False


async def _start_turn(app):
    """Mirror on_input_submitted without blocking the Pilot: run the
    agent turn as a background task."""
    app._busy = True
    app.messages.append({"role": "user", "content": "schreibe out.txt"})
    task = asyncio.create_task(
        app._run_agent_streaming(app.query_one("#transcript"))
    )
    return task


async def _wait_for(app, cond, tries=200):
    for _ in range(tries):
        if cond():
            return True
        await asyncio.sleep(0.02)
    return False


@pytest.mark.asyncio
async def test_permission_key_y_writes_file_and_restores_input(tmp_path):
    from textual.widgets import Input

    from eaccode.ui.repl import EaccodeApp

    app = EaccodeApp(workdir=tmp_path)
    agent, client = _make_agent(tmp_path, app._ask_permission_async)
    await _prepare_app(tmp_path, agent, app)

    async with app.run_test() as pilot:
        turn = await _start_turn(app)
        assert await _wait_for(app, lambda: getattr(
            app, "_pending_permission", None) is not None
        ), "permission prompt never became pending"
        assert app.query_one("#input", Input).disabled is False

        await pilot.press("y")
        assert await _wait_for(app, lambda: getattr(
            app, "_pending_permission", None) is None
        ), "permission never resolved after pressing y"

        assert (tmp_path / "out.txt").read_text(encoding="utf-8") \
            == "permission-ok"
        assert app.query_one("#input", Input).disabled is False
        assert app.query_one("#input", Input).has_focus

        await asyncio.wait_for(turn, timeout=15)
        assert client.calls == 2


@pytest.mark.asyncio
async def test_permission_escape_denies(tmp_path):
    from textual.widgets import Input

    from eaccode.ui.repl import EaccodeApp

    app = EaccodeApp(workdir=tmp_path)
    agent, _client = _make_agent(tmp_path, app._ask_permission_async)
    await _prepare_app(tmp_path, agent, app)

    async with app.run_test() as pilot:
        turn = await _start_turn(app)
        assert await _wait_for(app, lambda: getattr(
            app, "_pending_permission", None) is not None
        )

        await pilot.press("escape")
        assert await _wait_for(app, lambda: getattr(
            app, "_pending_permission", None) is None
        ), "permission never resolved after escape"

        assert not (tmp_path / "out.txt").exists()
        assert app.query_one("#input", Input).disabled is False
        await asyncio.wait_for(turn, timeout=15)


@pytest.mark.asyncio
async def test_y_is_normal_text_when_no_permission_pending(tmp_path):
    """The priority bindings must be gone after the ask settles —
    typing y in the Input must work again."""
    from textual.widgets import Input

    from eaccode.ui.repl import EaccodeApp

    app = EaccodeApp(workdir=tmp_path)
    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        inp.focus()
        await pilot.press("y")
        assert inp.value == "y"
