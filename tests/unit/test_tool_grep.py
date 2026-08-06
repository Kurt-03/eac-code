"""Tests for the Grep tool (Task 3.6)."""
import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.grep import GrepInput, GrepTool


@pytest.mark.asyncio
async def test_grep_finds_lines(tmp_path):
    (tmp_path / "a.py").write_text("def foo():\n    pass\n")
    (tmp_path / "b.py").write_text("def bar():\n    pass\n")
    tool = GrepTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(GrepInput(pattern="def "), ctx)
    assert "a.py" in result.content
    assert "b.py" in result.content
    assert "foo" in result.content


@pytest.mark.asyncio
async def test_grep_no_matches(tmp_path):
    (tmp_path / "a.py").write_text("nothing here")
    tool = GrepTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(GrepInput(pattern="zzz"), ctx)
    assert result.is_error is False


@pytest.mark.asyncio
async def test_grep_single_file(tmp_path):
    f = tmp_path / "target.py"
    f.write_text("line one\nsecret line\ntarget\n")
    (tmp_path / "other.py").write_text("target\n")
    tool = GrepTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(GrepInput(pattern="secret", path=str(f)), ctx)
    assert "secret line" in result.content
    assert "other.py" not in result.content


@pytest.mark.asyncio
async def test_grep_with_context_lines(tmp_path):
    (tmp_path / "f.py").write_text("a\nTARGET\nb\n")
    tool = GrepTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(GrepInput(pattern="TARGET", context=1), ctx)
    assert "a" in result.content
    assert "b" in result.content
