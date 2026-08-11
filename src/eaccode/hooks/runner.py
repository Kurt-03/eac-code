"""Hook runner (P0.10) — subprocess execution with timeout + output spill.

Each hook receives the event name and a few KEY=VALUE pairs on stdin
(one per line), e.g.::

    event=pre_tool_use
    tool=write
    workdir=/path/to/project

Hook stdout is captured; for PostToolUse it spills into the tool result
so the agent sees it. Failures are collected, never raised — a broken
hook must not break the agent.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from eaccode._subprocess_compat import IS_WINDOWS, windows_detach_flags

HOOK_TIMEOUT_S = 10.0


@dataclass
class HookResult:
    event: str
    hook: Path
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.error


def _run_one(event: str, hook: Path, cwd: Path,
             env_extra: dict[str, str], timeout: float) -> HookResult:
    payload = "\n".join(
        f"{k}={v}" for k, v in {"event": event, **env_extra}.items()
    )
    kwargs: dict = {
        "input": payload,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "cwd": str(cwd),
        "timeout": timeout,
    }
    if IS_WINDOWS:
        kwargs["creationflags"] = windows_detach_flags()
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.run([str(hook)], **kwargs)
        return HookResult(event, hook, proc.returncode, proc.stdout, proc.stderr)
    except OSError:
        # Windows cannot execute script files directly (WinError 193) —
        # fall back to the POSIX sh that ships with git-bash.
        try:
            proc = subprocess.run(["sh", str(hook)], **kwargs)
            return HookResult(event, hook, proc.returncode, proc.stdout,
                              proc.stderr)
        except (OSError, subprocess.SubprocessError) as e:
            return HookResult(event, hook, error=f"cannot run: {e}")
    except subprocess.TimeoutExpired:
        return HookResult(event, hook, error=f"timed out after {timeout}s")
    except subprocess.SubprocessError as e:
        return HookResult(event, hook, error=f"cannot run: {e}")


def run_hooks(
    event: str,
    cwd: Path,
    env_extra: dict[str, str] | None = None,
    hooks_dir: Path | None = None,
    timeout: float = HOOK_TIMEOUT_S,
) -> list[HookResult]:
    """Run every hook for *event*; returns results (never raises)."""
    if hooks_dir is None:
        return []
    from eaccode.hooks.registry import hook_for_event

    hooks = hook_for_event(hooks_dir, event)
    if not hooks:
        return []
    return [
        _run_one(event, hook, cwd, env_extra or {}, timeout)
        for hook in hooks
    ]


def spill_output(results: list[HookResult]) -> str:
    """PostToolUse spill: non-empty hook stdout, joined for the result."""
    chunks = [r.stdout.strip() for r in results if r.stdout.strip()]
    return "\n".join(chunks) if chunks else ""
