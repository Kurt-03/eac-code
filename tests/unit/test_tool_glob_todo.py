"""Tests for the built-in Glob and TodoWrite tools (Task 3.6)."""
import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.glob import GlobInput, GlobTool
from eaccode.tools.builtin.todo import TodoItem, TodoWriteInput, TodoWriteTool


@pytest.mark.asyncio
async def test_glob_finds_files(tmp_path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("x")
    (tmp_path / "c.txt").write_text("x")
    tool = GlobTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(GlobInput(pattern="*.py"), ctx)
    assert "a.py" in result.content
    assert "b.py" in result.content
    assert "c.txt" not in result.content


@pytest.mark.asyncio
async def test_glob_recursive(tmp_path):
    sub = tmp_path / "src" / "deep"
    sub.mkdir(parents=True)
    (sub / "x.py").write_text("x")
    tool = GlobTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(GlobInput(pattern="**/*.py"), ctx)
    assert "x.py" in result.content


@pytest.mark.asyncio
async def test_glob_no_matches(tmp_path):
    tool = GlobTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(GlobInput(pattern="*.nope"), ctx)
    assert result.is_error is False
    assert "No files found" in result.content


@pytest.mark.asyncio
async def test_todo_write_tracks_items(tmp_path):
    tool = TodoWriteTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(
        TodoWriteInput(
            todos=[
                TodoItem(status="in_progress", content="fix auth"),
                TodoItem(status="pending", content="write tests"),
            ]
        ),
        ctx,
    )
    assert result.is_error is False
    assert "fix auth" in result.content
    assert "write tests" in result.content
