"""Tests for the process tool (Phase I.2)."""

import sys
import time

import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.process import ProcessInput, ProcessTool


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path)


@pytest.mark.asyncio
async def test_spawn_status_kill_cycle(ctx, tmp_path):
    tool = ProcessTool()
    quoted = f'"{sys.executable}"'
    sleeper = tmp_path / "sleeper.py"
    sleeper.write_text("import time; time.sleep(60)\n", encoding="utf-8")
    r = await tool.run(ProcessInput(
        action="spawn", key="srv",
        command=f"{quoted} {sleeper}"
    ), ctx)
    assert "Started" in r.content
    assert "pid" in r.content

    r = await tool.run(ProcessInput(action="status", key="srv"), ctx)
    assert "running" in r.content

    r = await tool.run(ProcessInput(action="list"), ctx)
    assert "srv" in r.content

    r = await tool.run(ProcessInput(action="kill", key="srv"), ctx)
    assert "Killed" in r.content

    r = await tool.run(ProcessInput(action="remove", key="srv"), ctx)
    assert "Removed" in r.content


@pytest.mark.asyncio
async def test_spawn_requires_command(ctx):
    tool = ProcessTool()
    r = await tool.run(ProcessInput(action="spawn", key="x"), ctx)
    assert r.is_error is True
    assert "command" in r.content


@pytest.mark.asyncio
async def test_unknown_action(ctx):
    tool = ProcessTool()
    r = await tool.run(ProcessInput(action="frobnicate"), ctx)
    assert r.is_error is True


@pytest.mark.asyncio
async def test_status_unknown_process(ctx):
    tool = ProcessTool()
    r = await tool.run(ProcessInput(action="status", key="nope"), ctx)
    assert r.is_error is True
    assert "No process" in r.content


@pytest.mark.asyncio
async def test_poll_short_command_captures_output(ctx, tmp_path):
    tool = ProcessTool()
    script = tmp_path / "hello.py"
    script.write_text("print('hello from process')\n", encoding="utf-8")
    quoted = f'"{sys.executable}"'
    r = await tool.run(ProcessInput(
        action="spawn", key="hi",
        command=f"{quoted} {script}",
    ), ctx)
    assert r.is_error is False
    # Give the child a moment, then poll.
    time.sleep(0.4)
    r = await tool.run(ProcessInput(action="poll", key="hi", timeout=2.0), ctx)
    assert "hello from process" in r.content or "exited" in r.content
    await tool.run(ProcessInput(action="kill", key="hi"), ctx)
    await tool.run(ProcessInput(action="remove", key="hi"), ctx)


@pytest.mark.asyncio
async def test_poll_running_returns_state(ctx, tmp_path):
    tool = ProcessTool()
    quoted = f'"{sys.executable}"'  # shell=True + spaces in path
    sleeper = tmp_path / "sleeper.py"
    sleeper.write_text("import time; time.sleep(30)\n", encoding="utf-8")
    await tool.run(ProcessInput(
        action="spawn", key="long",
        command=f"{quoted} {sleeper}",
    ), ctx)
    r = await tool.run(ProcessInput(action="poll", key="long", timeout=0.2), ctx)
    assert "running" in r.content
    await tool.run(ProcessInput(action="kill", key="long"), ctx)
    await tool.run(ProcessInput(action="remove", key="long"), ctx)
