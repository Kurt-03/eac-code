"""Bash tool — execute shell commands with timeout + exit codes.

Runs in a worker thread via asyncio.to_thread: asyncio.create_subprocess_*
is broken on Windows (errno 9 with the default Proactor loop, and NOT
implemented at all with the Selector loop), so the sync subprocess module
is the only reliable cross-platform path.

Windows hardening (Phase A.2, ported from Hermes _subprocess_compat):
- CREATE_NO_WINDOW on Windows — a console-subsystem child inherits the
  Textual REPL's console handle; without the flag the child can crash the
  parent's captured pipes with errno 9 / EBADF when the console closes.
- Bounded communicate(timeout) + process-tree kill on timeout — a
  suspended grandchild holding the captured pipe handles would otherwise
  keep the reader threads blocked forever (unbounded run() cleanup).
- DEVNULL stdin: the child must never read from the terminal — in the REPL
  that handle belongs to the UI (errno 9 / input stealing).
- git invocations get GIT_TERMINAL_PROMPT=0 / GCM_INTERACTIVE=Never so a
  private remote can't hang the tool on a credential prompt.
"""

from __future__ import annotations

import asyncio
import os
import subprocess

from pydantic import BaseModel, Field

from eaccode._subprocess_compat import (
    IS_WINDOWS,
    kill_process_tree,
    noninteractive_git_env,
    windows_hide_flags,
)
from eaccode.tools.base import Tool, ToolContext, ToolResult


class BashInput(BaseModel):
    command: str = Field(description="Shell command to execute")
    timeout: float = Field(
        default=30.0, description="Timeout in seconds (max 600)"
    )
    description: str | None = Field(
        default=None, description="Optional human-readable description"
    )


class BashTool(Tool):
    name = "bash"
    description = (
        "Execute a shell command. Returns stdout, stderr, and exit code. "
        "Set timeout in seconds (default 30, max 600)."
    )
    input_model = BashInput
    requires_permission = True  # always gated by the policy engine

    async def run(self, input: BashInput, ctx: ToolContext) -> ToolResult:
        timeout = min(input.timeout, 600.0)
        env = noninteractive_git_env({**os.environ, **ctx.env})
        # DEVNULL: the child must never read from the terminal — in the REPL
        # that handle belongs to the UI (errno 9 / input stealing).
        popen_kwargs: dict = {}
        if IS_WINDOWS:
            # CREATE_NO_WINDOW: no console flash, no inherited console
            # handle that can EBADF the parent's pipes.
            popen_kwargs["creationflags"] = windows_hide_flags()
        try:
            proc = await asyncio.to_thread(
                self._run_bounded,
                input.command,
                str(ctx.workdir),
                env,
                timeout,
                popen_kwargs,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                content=f"Command timed out after {timeout}s",
                is_error=True,
                metadata={"exit_code": -1, "timed_out": True},
            )
        except Exception as e:
            return ToolResult(
                content=f"Error executing command: {type(e).__name__}: {e}",
                is_error=True,
                metadata={},
            )
        stdout_str = (proc.stdout or b"").decode("utf-8", errors="replace")
        stderr_str = (proc.stderr or b"").decode("utf-8", errors="replace")
        content = f"$ {input.command}\n{stdout_str}"
        if stderr_str:
            content += f"\n[stderr]\n{stderr_str}"
        return ToolResult(
            content=content,
            is_error=(proc.returncode != 0),
            metadata={
                "exit_code": proc.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str,
            },
        )

    @staticmethod
    def _run_bounded(
        command: str,
        cwd: str,
        env: dict,
        timeout: float,
        popen_kwargs: dict,
    ) -> subprocess.CompletedProcess:
        """Run a command with a bounded communicate + tree-kill on timeout.

        subprocess.run(timeout=...) calls an UNBOUNDED communicate() after
        killing the child — if a grandchild holds duplicates of the
        captured pipes, that join blocks forever.  Explicit
        communicate(timeout) + tree-kill + 1s bounded drain avoids the
        hang; if the pipes are still held afterwards they're abandoned
        (daemonic reader threads cost nothing).
        """
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            **popen_kwargs,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_process_tree(proc)
            try:
                stdout, stderr = proc.communicate(timeout=1)
            except Exception:
                stdout, stderr = b"", b""
            raise subprocess.TimeoutExpired(
                proc.args, timeout, output=stdout, stderr=stderr
            ) from None
        return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
