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


@pytest.mark.asyncio
async def test_bash_timeout_kills_process_tree(monkeypatch, tmp_path):
    """A timed-out command must tree-kill the child, not just the launcher."""
    killed = []

    def fake_kill_process_tree(proc):
        killed.append(proc.pid)

    monkeypatch.setattr(
        "eaccode.tools.builtin.bash.kill_process_tree", fake_kill_process_tree
    )
    tool = BashTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(BashInput(command="sleep 10", timeout=0.1), ctx)
    assert result.is_error is True
    assert result.metadata["timed_out"] is True
    assert killed  # tree-kill was invoked with the child's pid


@pytest.mark.asyncio
async def test_bash_passes_hidden_window_flags_on_windows(monkeypatch, tmp_path):
    """On Windows the child must get CREATE_NO_WINDOW (errno 9 guard)."""
    from eaccode.tools.builtin import bash as bash_mod

    captured = {}

    def fake_run_bounded(command, cwd, env, timeout, popen_kwargs):
        captured.update(popen_kwargs)
        return __import__("subprocess").CompletedProcess(command, 0, b"ok", b"")

    monkeypatch.setattr(bash_mod, "IS_WINDOWS", True)
    monkeypatch.setattr(bash_mod.BashTool, "_run_bounded", staticmethod(fake_run_bounded))
    tool = BashTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(BashInput(command="echo ok"), ctx)
    assert "ok" in result.content
    assert captured["creationflags"] & 0x08000000  # CREATE_NO_WINDOW


@pytest.mark.asyncio
async def test_bash_git_env_is_noninteractive(tmp_path):
    """git calls must never prompt for credentials (hang guard)."""
    from eaccode.tools.builtin import bash as bash_mod

    captured = {}

    def fake_run_bounded(command, cwd, env, timeout, popen_kwargs):
        captured["env"] = env
        return __import__("subprocess").CompletedProcess(command, 0, b"", b"")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(bash_mod.BashTool, "_run_bounded", staticmethod(fake_run_bounded))
    tool = BashTool()
    ctx = ToolContext(workdir=tmp_path)
    await tool.run(BashInput(command="git status"), ctx)
    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert captured["env"]["GCM_INTERACTIVE"] == "Never"
    monkeypatch.undo()
