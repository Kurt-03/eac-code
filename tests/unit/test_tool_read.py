"""Tests for the built-in Read tool (Task 3.2)."""

import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.read import ReadInput, ReadTool


@pytest.mark.asyncio
async def test_read_full_file(tmp_path):
    (tmp_path / "test.txt").write_text("hello\nworld\n")
    tool = ReadTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(ReadInput(path="test.txt"), ctx)
    assert "hello" in result.content
    assert "world" in result.content


@pytest.mark.asyncio
async def test_read_with_offset_and_limit(tmp_path):
    (tmp_path / "test.txt").write_text("\n".join(f"line {i}" for i in range(20)))
    tool = ReadTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(ReadInput(path="test.txt", offset=5, limit=3), ctx)
    assert "line 4" in result.content
    assert "line 6" in result.content
    assert "line 7" not in result.content


@pytest.mark.asyncio
async def test_read_nonexistent_file(tmp_path):
    tool = ReadTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(ReadInput(path="missing.txt"), ctx)
    assert result.is_error is True


@pytest.mark.asyncio
async def test_read_absolute_path(tmp_path):
    f = tmp_path / "abs.txt"
    f.write_text("absolute")
    tool = ReadTool()
    ctx = ToolContext(workdir=tmp_path / "sub")
    result = await tool.run(ReadInput(path=str(f)), ctx)
    assert "absolute" in result.content


@pytest.mark.asyncio
async def test_read_reports_total_lines(tmp_path):
    (tmp_path / "f.txt").write_text("a\nb\nc")
    tool = ReadTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(ReadInput(path="f.txt"), ctx)
    assert result.metadata["total_lines"] == 3
