"""Tests for clarify + execute_code tools (Phase C.1/C.2)."""

import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.clarify import ClarifyInput, ClarifyTool
from eaccode.tools.builtin.execute_code import ExecuteCodeInput, ExecuteCodeTool


@pytest.mark.asyncio
async def test_clarify_returns_question(tmp_path):
    tool = ClarifyTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(
        ClarifyInput(question="Which port should the server use?"), ctx
    )
    assert result.is_error is False
    assert "Which port" in result.content
    assert "answer" in result.content.lower()  # instructs the agent to answer


@pytest.mark.asyncio
async def test_execute_code_runs_python(tmp_path):
    tool = ExecuteCodeTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(ExecuteCodeInput(code="print(6 * 7)"), ctx)
    assert result.is_error is False
    assert "42" in result.content


@pytest.mark.asyncio
async def test_execute_code_captures_errors(tmp_path):
    tool = ExecuteCodeTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(ExecuteCodeInput(code="1/0"), ctx)
    assert result.is_error is True
    assert "ZeroDivisionError" in result.content


@pytest.mark.asyncio
async def test_execute_code_timeout(tmp_path):
    tool = ExecuteCodeTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(
        ExecuteCodeInput(code="import time; time.sleep(30)", timeout=1.0), ctx
    )
    assert result.is_error is True
    assert "timed out" in result.content
