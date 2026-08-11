"""Tests for checkpoints (Phase C.4) + delegate wiring."""

import asyncio

import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.delegate import (
    DelegateInput,
    DelegateTask,
    DelegateTool,
    cancel_all_background,
    collect_background_results,
)
from eaccode.tools.checkpoints import (
    list_checkpoints,
    restore_checkpoint,
    save_checkpoint,
)


def test_save_and_list_checkpoints(tmp_path):
    f = tmp_path / "main.py"
    f.write_text("v1")
    cp = save_checkpoint(tmp_path, f)
    assert cp is not None and cp.exists()
    assert len(list_checkpoints(tmp_path)) == 1


def test_no_checkpoint_for_missing_file(tmp_path):
    assert save_checkpoint(tmp_path, tmp_path / "nope.py") is None


def test_restore_checkpoint(tmp_path):
    f = tmp_path / "main.py"
    f.write_text("v1")
    cp = save_checkpoint(tmp_path, f)
    f.write_text("v2 broken")
    assert restore_checkpoint(tmp_path, cp)
    assert f.read_text() == "v1"


def test_restore_invalid_name_fails(tmp_path):
    bogus = tmp_path / "nope.bak"
    bogus.write_text("x")
    assert restore_checkpoint(tmp_path, bogus) is False


@pytest.mark.asyncio
async def test_delegate_requires_builder(tmp_path):
    tool = DelegateTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(DelegateInput(goal="do something"), ctx)
    assert result.is_error is True
    assert "not available" in result.content


@pytest.mark.asyncio
async def test_delegate_runs_subagent(tmp_path):
    class FakeConfig:
        writer_id = "main"

    class FakeSubAgent:
        config = FakeConfig()

        async def run(self, messages):
            from eaccode.agent.loop import AgentResult
            from eaccode.llm.client import TokenUsage

            return AgentResult(
                final_text="subagent result!",
                messages=[],
                usage=TokenUsage(),
                turns=1,
                cost_usd=0.0,
            )

    async def fake_builder(workdir, max_turns=15):
        return FakeSubAgent(), None, None

    tool = DelegateTool()
    ctx = ToolContext(workdir=tmp_path, config={"delegate_builder": fake_builder})
    result = await tool.run(DelegateInput(goal="go"), ctx)
    assert result.is_error is False
    assert "subagent result!" in result.content


@pytest.mark.asyncio
async def test_batch_mode_parallel_tasks(tmp_path):
    """Phase I.13: tasks array runs in parallel and consolidates results."""
    from eaccode.tools.builtin.delegate import DelegateInput, DelegateTool

    results = []

    async def fake_builder(workdir, max_turns=15):
        from eaccode.agent.loop import AgentConfig, AgentLoop
        from eaccode.config.settings import PermissionMode
        from eaccode.llm.client import CompletionResponse, TokenUsage
        from eaccode.permissions.policy import PolicyEngine
        from eaccode.permissions.rules import RuleSet
        from eaccode.tools.base import ToolRegistry

        class FakeClient:
            def complete(self, req):
                goal = req.messages[-1].text
                results.append(goal)
                return CompletionResponse(
                    text=f"done: {goal[:20]}", tool_calls=[],
                    stop_reason="end_turn", usage=TokenUsage(), model="fake",
                )

        reg = ToolRegistry()
        agent = AgentLoop(FakeClient(), reg,
                          PolicyEngine(mode=PermissionMode.BYPASS_PERMISSIONS,
                                       rules=RuleSet()),
                          AgentConfig(workdir=workdir, max_turns=3))
        return agent, reg, PolicyEngine(mode=PermissionMode.BYPASS_PERMISSIONS,
                                        rules=RuleSet())

    tool = DelegateTool()
    tool.delegate_builder = fake_builder
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(DelegateInput(tasks=[
        DelegateTask(goal="task A"),
        DelegateTask(goal="task B"),
    ]), ctx)
    assert result.is_error is False
    assert "task A" in result.content
    assert "task B" in result.content
    assert len(results) == 2  # both subagents ran


# ---------------------------------------------------------------- C.4


@pytest.mark.asyncio
async def test_background_delegation_returns_immediately(tmp_path):
    """C.4: background=True returns right away; the result is collected
    by the loop later."""
    results: list[str] = []

    async def fake_builder(workdir, max_turns=15):
        from eaccode.agent.loop import AgentConfig, AgentLoop
        from eaccode.config.settings import PermissionMode
        from eaccode.llm.client import TokenUsage
        from eaccode.permissions.policy import PolicyEngine
        from eaccode.permissions.rules import RuleSet
        from eaccode.tools.base import ToolRegistry

        class FakeClient:
            def complete(self, req):
                results.append(req.messages[-1].text)
                return CompletionResponse(
                    text="bg done", tool_calls=[], stop_reason="end_turn",
                    usage=TokenUsage(), model="fake",
                )

        return AgentLoop(
            FakeClient(), ToolRegistry(),
            PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet()),
            AgentConfig(workdir=workdir, max_turns=3),
        ), None, None

    tool = DelegateTool()
    tool.delegate_builder = fake_builder
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(
        DelegateInput(goal="background task", background=True), ctx
    )
    assert result.is_error is False
    assert "background" in result.content
    assert result.metadata.get("delegation_id") == 1
    # Let the background task finish, then collect.
    for _ in range(50):
        if collect_background_results():
            break
        await asyncio.sleep(0.01)
    collected = collect_background_results()
    assert any("[delegation #1]" in line for line in collected)
    assert results == ["background task"]


@pytest.mark.asyncio
async def test_background_failure_is_collected(tmp_path):
    async def broken_builder(workdir, max_turns=15):
        raise RuntimeError("boom")

    tool = DelegateTool()
    tool.delegate_builder = broken_builder
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(
        DelegateInput(goal="will fail", background=True), ctx
    )
    assert result.is_error is False  # the delegation itself succeeded
    for _ in range(50):
        if collect_background_results():
            break
        await asyncio.sleep(0.01)
    collected = collect_background_results()
    assert any("failed" in line for line in collected)


def test_cancel_all_background_clears():
    cancel_all_background()  # must not raise with nothing running
    assert collect_background_results() == []
