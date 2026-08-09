"""Regression for the errno 9 / EBADF class (Phase A.7).

The user hit "Bad file descriptor" on tool calls inside the REPL. Root
causes fixed in Phase A:

1. Console children inherited the Textual console handle without
   CREATE_NO_WINDOW → pipes died with EBADF when the console closed.
2. subprocess.run(timeout=...) called an UNBOUNDED communicate() after
   killing the child; a suspended grandchild holding the captured pipes
   blocked the reader threads forever.

These tests simulate the failure shape: run a subprocess that outlives
its timeout, then immediately run another subprocess through the same
tool — the second must succeed with no EBADF and no hang.
"""

import subprocess
import sys

import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.bash import BashInput, BashTool


@pytest.mark.asyncio
async def test_bash_survives_timeout_then_reruns(tmp_path):
    """After a timeout+tree-kill, the next bash call must work cleanly.

    Before Phase A.2 the timed-out child could leave a suspended
    grandchild holding the captured pipe handles; the next run then hit
    OSError(9) 'Bad file descriptor' or hung forever on the reader join.
    """
    tool = BashTool()
    ctx = ToolContext(workdir=tmp_path)

    # 1) A command that spawns a child and outlives the timeout.
    timeout_result = await tool.run(
        BashInput(command="python -c 'import time; time.sleep(5)'", timeout=0.3), ctx
    )
    assert timeout_result.is_error is True
    assert timeout_result.metadata["timed_out"] is True

    # 2) Immediately run another command through the same tool — this is
    #    the call that crashed with errno 9 before the fix.
    result = await tool.run(BashInput(command="echo still-alive"), ctx)
    assert result.is_error is False
    assert "still-alive" in result.content


@pytest.mark.asyncio
async def test_bash_tree_kill_actually_terminates(tmp_path):
    """The child must be GONE after the timeout — no zombie holding pipes."""
    import time

    tool = BashTool()
    ctx = ToolContext(workdir=tmp_path)
    start = time.monotonic()
    await tool.run(BashInput(command="python -c 'import time; time.sleep(30)'", timeout=0.3), ctx)
    elapsed = time.monotonic() - start
    # The bounded drain must not block: whole flow well under the sleep.
    assert elapsed < 10.0


@pytest.mark.asyncio
async def test_bash_loop_of_tool_calls_stays_healthy(tmp_path):
    """10 bash calls in a row — the classic tool-loop shape from the bug
    report ("erstelle mir eine test.txt auf dem Desktop")."""
    tool = BashTool()
    ctx = ToolContext(workdir=tmp_path)
    for i in range(10):
        result = await tool.run(BashInput(command=f"echo call-{i}"), ctx)
        assert result.is_error is False
        assert f"call-{i}" in result.content


@pytest.mark.asyncio
async def test_execute_code_survives_timeout_then_reruns(tmp_path):
    """Same shape for execute_code (Phase A.3)."""
    from eaccode.tools.builtin.execute_code import ExecuteCodeInput, ExecuteCodeTool

    tool = ExecuteCodeTool()
    ctx = ToolContext(workdir=tmp_path)

    timeout_result = await tool.run(
        ExecuteCodeInput(code="import time; time.sleep(5)", timeout=0.3), ctx
    )
    assert timeout_result.is_error is True

    result = await tool.run(ExecuteCodeInput(code="print('ok-again')"), ctx)
    assert result.is_error is False
    assert "ok-again" in result.content


def test_windows_flags_do_not_break_plain_subprocess(tmp_path):
    """CREATE_NO_WINDOW must not change normal subprocess semantics."""
    from eaccode._subprocess_compat import windows_hide_flags

    flags = windows_hide_flags()
    kwargs = {"creationflags": flags} if flags else {}
    result = subprocess.run(
        [sys.executable, "-c", "print('hello')"],
        capture_output=True, text=True, cwd=str(tmp_path), **kwargs,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "hello"
