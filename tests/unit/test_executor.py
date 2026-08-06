"""Tests for the ToolExecutor (Task 3.7)."""

import pytest

from eaccode.tools.base import ToolRegistry
from eaccode.tools.builtin.read import ReadTool
from eaccode.tools.executor import ToolExecutor


@pytest.mark.asyncio
async def test_executor_routes_to_correct_tool(tmp_path):
    reg = ToolRegistry()
    reg.register(ReadTool())
    executor = ToolExecutor(reg)
    (tmp_path / "x.txt").write_text("hi")
    result = await executor.execute("read", {"path": "x.txt"}, tmp_path)
    assert "hi" in result.content


@pytest.mark.asyncio
async def test_executor_handles_unknown_tool(tmp_path):
    reg = ToolRegistry()
    executor = ToolExecutor(reg)
    result = await executor.execute("nonexistent", {}, tmp_path)
    assert result.is_error is True
    assert "unknown tool" in result.content.lower()


@pytest.mark.asyncio
async def test_executor_handles_bad_arguments(tmp_path):
    reg = ToolRegistry()
    reg.register(ReadTool())
    executor = ToolExecutor(reg)
    result = await executor.execute("read", {"path": 123}, tmp_path)  # wrong type
    assert result.is_error is True


@pytest.mark.asyncio
async def test_executor_missing_required_argument(tmp_path):
    reg = ToolRegistry()
    reg.register(ReadTool())
    executor = ToolExecutor(reg)
    result = await executor.execute("read", {}, tmp_path)  # path fehlt
    assert result.is_error is True
    assert "invalid arguments" in result.content.lower()


@pytest.mark.asyncio
async def test_executor_returns_available_tools_on_unknown(tmp_path):
    reg = ToolRegistry()
    reg.register(ReadTool())
    executor = ToolExecutor(reg)
    result = await executor.execute("nope", {}, tmp_path)
    assert "read" in result.content  # hilfreiche Liste
