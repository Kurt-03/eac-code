"""Tests for the built-in Write tool (Task 3.3)."""
import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.write import WriteInput, WriteTool


@pytest.mark.asyncio
async def test_write_creates_file(tmp_path):
    tool = WriteTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(WriteInput(path="new.txt", content="hi"), ctx)
    assert result.is_error is False
    assert (tmp_path / "new.txt").read_text() == "hi"


@pytest.mark.asyncio
async def test_write_overwrites(tmp_path):
    (tmp_path / "existing.txt").write_text("old")
    tool = WriteTool()
    ctx = ToolContext(workdir=tmp_path)
    await tool.run(WriteInput(path="existing.txt", content="new"), ctx)
    assert (tmp_path / "existing.txt").read_text() == "new"


@pytest.mark.asyncio
async def test_write_creates_parent_dirs(tmp_path):
    tool = WriteTool()
    ctx = ToolContext(workdir=tmp_path)
    await tool.run(WriteInput(path="deep/nested/file.txt", content="x"), ctx)
    assert (tmp_path / "deep" / "nested" / "file.txt").read_text() == "x"


@pytest.mark.asyncio
async def test_write_reports_bytes(tmp_path):
    tool = WriteTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(WriteInput(path="f.txt", content="hello"), ctx)
    assert result.metadata["bytes"] == 5


def test_write_requires_permission():
    assert WriteTool.requires_permission is True
