"""Tests for the built-in Edit tool (Task 3.4)."""
import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.edit import EditInput, EditTool


@pytest.mark.asyncio
async def test_edit_replaces_unique_match(tmp_path):
    (tmp_path / "f.txt").write_text("foo\nbar\nbaz")
    tool = EditTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(
        EditInput(path="f.txt", old_string="bar", new_string="BAR"), ctx
    )
    assert result.is_error is False
    assert (tmp_path / "f.txt").read_text() == "foo\nBAR\nbaz"


@pytest.mark.asyncio
async def test_edit_fails_on_no_match(tmp_path):
    (tmp_path / "f.txt").write_text("foo")
    tool = EditTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(
        EditInput(path="f.txt", old_string="missing", new_string="x"), ctx
    )
    assert result.is_error is True
    assert "not found" in result.content.lower()


@pytest.mark.asyncio
async def test_edit_fails_on_ambiguous_match(tmp_path):
    (tmp_path / "f.txt").write_text("foo\nfoo\n")
    tool = EditTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(
        EditInput(path="f.txt", old_string="foo", new_string="bar"), ctx
    )
    assert result.is_error is True
    assert "unique" in result.content.lower() or "matches" in result.content.lower()


@pytest.mark.asyncio
async def test_edit_missing_file(tmp_path):
    tool = EditTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(
        EditInput(path="nope.txt", old_string="a", new_string="b"), ctx
    )
    assert result.is_error is True
