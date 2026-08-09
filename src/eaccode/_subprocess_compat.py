"""Windows subprocess compatibility helpers.

Ported from Hermes' ``hermes_cli/_subprocess_compat.py`` (MIT, Aug 2026).
Several common subprocess patterns break silently-or-loudly on Windows:

* ``subprocess.run(["npm", ...])`` fails with WinError 193 on ``npm.cmd``
  unless PATHEXT resolution (``shutil.which``) is used.
* ``start_new_session=True`` is silently ignored on Windows; the Windows
  equivalent is the ``CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW``
  creationflags bundle.
* Every ``subprocess.Popen`` of a console-subsystem child on Windows
  flashes a cmd window unless ``CREATE_NO_WINDOW`` is passed.
* Killing the direct child leaves descendants holding captured pipe
  handles → the pipes never reach EOF and ``communicate()`` blocks
  forever. The fix is a process-tree kill (``taskkill /T /F`` on Windows,
  ``os.killpg`` on POSIX).

**All helpers are no-ops on non-Windows** — calling them in Linux/macOS
code paths is safe by design ("do no damage on POSIX" guarantee).
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence

__all__ = [
    "IS_WINDOWS",
    "bounded_git_probe",
    "kill_process_tree",
    "noninteractive_git_env",
    "resolve_node_command",
    "suppress_platform_ver_console",
    "windows_detach_flags",
    "windows_detach_flags_without_breakaway",
    "windows_detach_popen_kwargs",
    "windows_hide_flags",
]

IS_WINDOWS = sys.platform == "win32"

# Win32 CreationFlags — defined here rather than imported from subprocess
# because CREATE_NO_WINDOW and DETACHED_PROCESS aren't guaranteed to be
# present on stdlib subprocess on older Pythons or non-Windows builds.
_CREATE_NEW_PROCESS_GROUP = 0x00000200
# DETACHED_PROCESS is intentionally NOT part of any flag bundle — combining
# it with CREATE_NO_WINDOW makes the no-window bit dead (MSDN: CREATE_NO_WINDOW
# "is ignored if used with either CREATE_NEW_CONSOLE or DETACHED_PROCESS"),
# and a truly console-less child makes every descendant allocate a visible
# flashing console. See Hermes' _subprocess_compat docstring for the full
# root-cause analysis (bugs #54220 / #56747).
_CREATE_NO_WINDOW = 0x08000000
# Escape any Win32 job object the parent process belongs to (Electron,
# Tauri, dev shells wrap children in job objects). Without this, a
# "detached" child dies when the parent's job is torn down.
_CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def windows_hide_flags() -> int:
    """Return Win32 creationflags that merely hide the child's console
    window without detaching the child.  0 on non-Windows.

    Use for short-lived console apps spawned as part of a larger
    operation (git probes, version checks) where we want no flash but
    also want to collect stdout/exit code synchronously.  The child
    stays in the parent's process group and job, so Ctrl+C and job
    teardown propagate normally.  ``capture_output=True`` works with
    this bundle.
    """
    if not IS_WINDOWS:
        return 0
    return _CREATE_NO_WINDOW


def windows_detach_flags() -> int:
    """Return Win32 creationflags that detach a child from the parent
    console and process group without leaving it console-less.  0 on
    non-Windows.

    ``CREATE_NEW_PROCESS_GROUP`` — the child has its own process group,
    so Ctrl+C in the parent console doesn't propagate.
    ``CREATE_NO_WINDOW`` — the child owns a hidden console that all its
    descendants inherit, so no visible flashes ever appear.
    ``CREATE_BREAKAWAY_FROM_JOB`` — escape any job object the parent is
    in, so the child survives the parent's death.
    """
    if not IS_WINDOWS:
        return 0
    return (
        _CREATE_NEW_PROCESS_GROUP
        | _CREATE_NO_WINDOW
        | _CREATE_BREAKAWAY_FROM_JOB
    )


def windows_detach_flags_without_breakaway() -> int:
    """Same as :func:`windows_detach_flags` minus ``CREATE_BREAKAWAY_FROM_JOB``.

    A process in a job that disallows breakaway (no
    ``JOB_OBJECT_LIMIT_BREAKAWAY_OK``) will see ``ERROR_ACCESS_DENIED``
    from CreateProcess, surfacing as ``PermissionError`` on Popen.
    Callers that want to recover retry without the breakaway bit.
    """
    if not IS_WINDOWS:
        return 0
    return _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW


def windows_detach_popen_kwargs() -> dict:
    """Return a dict of Popen kwargs that detach a child on Windows and
    fall back to the POSIX equivalent (``start_new_session=True``) on
    Linux/macOS.

    Replaces the unsafe-on-Windows pattern ``Popen(..., start_new_session=True)``,
    which silently fails to detach on Windows.
    """
    if IS_WINDOWS:
        return {"creationflags": windows_detach_flags()}
    return {"start_new_session": True}


def resolve_node_command(name: str, argv: Sequence[str]) -> list[str]:
    """Resolve a Node-ecosystem command name (npm/npx/yarn/...) to an
    absolute-path argv.

    On Windows these ship as ``.cmd`` batch shims; ``Popen(["npm", ...])``
    fails with WinError 193. ``shutil.which`` resolves them via PATHEXT
    to a path CreateProcessW accepts.  Returns the bare name when not
    found, so the caller can surface a readable error.
    """
    resolved = shutil.which(name)
    if resolved:
        return [resolved, *argv]
    return [name, *argv]


def noninteractive_git_env(
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Environment for *internal* git invocations that must never prompt.

    When a remote is private or misconfigured, git's default behavior is
    to prompt on the inherited terminal (or via askpass), which silently
    hangs the operation until its timeout.  Ported from
    openai/codex#34540 / #34612.

    * ``GIT_TERMINAL_PROMPT=0`` — git fails fast with "terminal prompts
      disabled" instead of prompting for credentials.
    * ``GCM_INTERACTIVE=Never`` — Git Credential Manager (the default
      credential helper on Windows installs) never pops its own dialog.

    Pair with ``stdin=subprocess.DEVNULL`` so git (and any credential
    helper it spawns) can't read the parent's inherited stdin.
    """
    env = dict(base if base is not None else os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return env


def suppress_platform_ver_console() -> None:
    """Stub out ``platform._syscmd_ver`` on Windows so it can never flash
    a console window.  No-op on non-Windows.

    CPython's ``platform.win32_ver()`` — reached by ``platform.uname()``,
    ``platform.version()``, and ``platform.platform()`` — unconditionally
    shells out ``cmd /c ver`` with no ``CREATE_NO_WINDOW``.  From a
    windowless parent that allocates a fresh *visible* console: one
    flashing ``cmd`` window per process, triggered by any dependency that
    merely touches ``platform.uname()`` at import time.

    Call early, before heavyweight imports — the flash typically happens
    during a dependency's import, not from our own code.
    """
    if not IS_WINDOWS:
        return
    try:
        import platform

        if hasattr(platform, "_syscmd_ver"):
            def _quiet_syscmd_ver(system="", release="", version="",
                                  supported_platforms=("win32", "win16", "dos")):
                return system, release, version

            platform._syscmd_ver = _quiet_syscmd_ver
    except Exception:
        # Purely cosmetic hardening — never let it break startup.
        pass


def kill_process_tree(proc: subprocess.Popen) -> None:
    """Best-effort terminate *proc* and its descendants on both platforms.

    ``proc.kill()`` alone only terminates the direct child.  On Windows a
    suspended descendant can survive holding duplicates of the captured
    pipe handles, which keeps the pipes from reaching EOF and leaks two
    reader threads + the process per fired timeout.  ``taskkill /T /F``
    takes the whole tree down so the bounded drain that follows can
    actually reach EOF.  On POSIX the same class exists: killing the
    launcher leaves descendants (credential helpers, ``git-remote-https``,
    hook children) running and holding the pipe write ends.

    All failures are swallowed — this is cleanup on an already-failing
    path, and the caller's contract is to fail open.
    """
    if not IS_WINDOWS:
        try:
            import signal as _signal

            pgid = os.getpgid(proc.pid)
            if pgid == proc.pid:
                os.killpg(pgid, _signal.SIGKILL)
        except Exception:
            pass
    with contextlib.suppress(OSError):
        proc.kill()
    if IS_WINDOWS:
        with contextlib.suppress(Exception):
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                timeout=2,
                check=False,
                creationflags=windows_hide_flags(),
            )


def bounded_git_probe(argv: Sequence[str], *, timeout: float) -> str:
    """Run a short, throwaway ``git`` probe and return stripped stdout, or
    ``""`` on ANY failure (nonzero exit, timeout, spawn error, decode error).

    This is the shared, deadlock-safe replacement for
    ``subprocess.run(["git", ...], timeout=...)`` at fail-open probe call
    sites.  Why not ``subprocess.run``: on Windows, ``run()``'s
    post-timeout cleanup calls an *unbounded* ``communicate()`` after
    killing git.  Killing the PATH-resolved launcher can leave a
    suspended descendant holding duplicates of the captured stdout/stderr
    handles, so the pipes never reach EOF and the reader-thread join
    blocks forever (Hermes issues #68609 / #66037; port of
    openai/codex#36793).

    The bounded flow: an explicit ``communicate(timeout)``, then on any
    failure a tree-kill plus a bounded 1s post-kill drain; if the pipes
    are still held after that, they're abandoned (the orphaned reader
    threads are daemonic and cost nothing).
    """
    _popen_kwargs: dict = (
        {"creationflags": windows_hide_flags()} if IS_WINDOWS else {"process_group": 0}
    )
    try:
        proc = subprocess.Popen(
            list(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=noninteractive_git_env(),
            **_popen_kwargs,
        )
    except Exception:
        return ""
    try:
        stdout, _ = proc.communicate(timeout=timeout)
    except Exception:
        # Timeout OR any other communicate() failure (torn-down pipe,
        # decode error): terminate the child + descendants and drain
        # bounded.  Leaving it running would leak the same
        # suspended-descendant class this guards.
        kill_process_tree(proc)
        with contextlib.suppress(Exception):
            proc.communicate(timeout=1)
        return ""
    return stdout.strip() if proc.returncode == 0 else ""
