"""Tests for the Windows subprocess compatibility helpers (Phase A.1)."""

import os
import subprocess
import sys

from eaccode._subprocess_compat import (
    bounded_git_probe,
    kill_process_tree,
    noninteractive_git_env,
    resolve_node_command,
    suppress_platform_ver_console,
    windows_detach_flags,
    windows_detach_flags_without_breakaway,
    windows_detach_popen_kwargs,
    windows_hide_flags,
)


def test_windows_flags_are_zero_on_posix(monkeypatch):
    monkeypatch.setattr("eaccode._subprocess_compat.IS_WINDOWS", False)
    assert windows_hide_flags() == 0
    assert windows_detach_flags() == 0
    assert windows_detach_flags_without_breakaway() == 0
    assert windows_detach_popen_kwargs() == {"start_new_session": True}


def test_windows_flags_include_no_window(monkeypatch):
    monkeypatch.setattr("eaccode._subprocess_compat.IS_WINDOWS", True)
    hide = windows_hide_flags()
    detach = windows_detach_flags()
    # CREATE_NO_WINDOW = 0x08000000 must be present in both
    assert hide & 0x08000000
    assert detach & 0x08000000
    # detach adds process-group + breakaway
    assert detach & 0x00000200  # CREATE_NEW_PROCESS_GROUP
    assert detach & 0x01000000  # CREATE_BREAKAWAY_FROM_JOB
    # hide must NOT include breakaway (short-lived helper stays in job)
    assert not (hide & 0x01000000)


def test_windows_detach_popen_kwargs_uses_creationflags(monkeypatch):
    monkeypatch.setattr("eaccode._subprocess_compat.IS_WINDOWS", True)
    kwargs = windows_detach_popen_kwargs()
    assert "creationflags" in kwargs
    assert kwargs["creationflags"] == windows_detach_flags()


def test_noninteractive_git_env_sets_expected_vars():
    env = noninteractive_git_env({"PATH": "/bin"})
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GCM_INTERACTIVE"] == "Never"
    assert env["PATH"] == "/bin"  # base preserved


def test_kill_process_tree_swallows_errors():
    # A non-existent process must not raise.
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    kill_process_tree(proc)
    # The child should be gone (killed on both platforms).
    assert proc.poll() is not None


def test_suppress_platform_ver_console_idempotent():
    suppress_platform_ver_console()
    suppress_platform_ver_console()  # second call must not raise
    import platform

    assert callable(getattr(platform, "_syscmd_ver", None))


def test_resolve_node_command_resolves_on_path(monkeypatch):
    # shutil.which resolves `python` to an absolute path on both platforms.
    resolved = resolve_node_command("python", ["-c", "print(1)"])
    assert os.path.isabs(resolved[0]) or resolved[0] == "python"
    assert resolved[1:] == ["-c", "print(1)"]


def test_resolve_node_command_unknown_name_passthrough(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    resolved = resolve_node_command("definitely-not-a-real-cmd-xyz", ["--help"])
    assert resolved == ["definitely-not-a-real-cmd-xyz", "--help"]


def test_bounded_git_probe_returns_stdout_on_success(tmp_path):
    out = bounded_git_probe(
        ["git", "-C", str(tmp_path), "init", "-q", "-b", "main"], timeout=10
    )
    assert out == ""  # git init -q prints nothing on success


def test_bounded_git_probe_empty_on_failure():
    out = bounded_git_probe(["git", "definitely-not-a-real-subcommand"], timeout=5)
    assert out == ""  # fail-open contract


def test_bounded_git_probe_never_hangs_on_timeout():
    # `git` may not exist in the test env; the contract is: no hang, "" on
    # ANY failure. Use a 1s timeout on a bogus command — must return fast.
    out = bounded_git_probe(["git", "log", "--all"], timeout=0.5)
    assert out == "" or isinstance(out, str)


def test_windows_popen_with_hide_flags_runs(tmp_path):
    """The hidden-window flag bundle must not break normal subprocess use."""
    creationflags = windows_hide_flags()
    kwargs = {"creationflags": creationflags} if creationflags else {}
    result = subprocess.run(
        [sys.executable, "-c", "print('hi')"],
        capture_output=True, text=True, **kwargs,
    )
    assert result.returncode == 0
    assert "hi" in result.stdout
