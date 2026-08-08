"""Tests for checkpoints (Phase C.4) + delegate wiring."""

import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.delegate import DelegateInput, DelegateTool
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
    class FakeSubAgent:
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
