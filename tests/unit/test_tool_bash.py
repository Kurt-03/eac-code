"""Tests for the built-in Bash tool (Task 3.5)."""
import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.bash import BashInput, BashTool


@pytest.mark.asyncio
async def test_bash_runs_simple_command(tmp_path):
    tool = BashTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(BashInput(command="echo hello"), ctx)
    assert "hello" in result.content
    assert result.is_error is False


@pytest.mark.asyncio
async def test_bash_returns_exit_code(tmp_path):
    tool = BashTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(BashInput(command="exit 1"), ctx)
    assert result.is_error is True
    assert result.metadata["exit_code"] == 1


@pytest.mark.asyncio
async def test_bash_timeout(tmp_path):
    tool = BashTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(BashInput(command="sleep 10", timeout=0.1), ctx)
    assert result.is_error is True
    assert result.metadata["timed_out"] is True


@pytest.mark.asyncio
async def test_bash_runs_in_workdir(tmp_path):
    (tmp_path / "marker.txt").write_text("here")
    tool = BashTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(BashInput(command="cat marker.txt"), ctx)
    assert "here" in result.content


@pytest.mark.asyncio
async def test_bash_captures_stderr(tmp_path):
    tool = BashTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(BashInput(command="echo oops 1>&2"), ctx)
    assert "oops" in result.content


def test_bash_requires_permission():
    assert BashTool.requires_permission is True
