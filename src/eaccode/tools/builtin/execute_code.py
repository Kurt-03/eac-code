"""execute_code tool — run Python in a worker thread.

Not a true sandbox (like Hermes' execute_code it runs locally), so the
tool description tells the model to keep it to trusted computations.
Runs via subprocess in a thread — reliable on Windows, DEVNULL stdin,
5-minute cap. Uses the same Windows hardening as the bash tool
(CREATE_NO_WINDOW + bounded communicate + tree-kill on timeout), so a
runaway child can't flash a console or hang the pipe readers (errno 9
class, Phase A.3).
"""

from __future__ import annotations

import asyncio
import os
import subprocess

from pydantic import BaseModel, Field

from eaccode._subprocess_compat import (
    IS_WINDOWS,
    kill_process_tree,
    windows_hide_flags,
)
from eaccode.tools.base import Tool, ToolContext, ToolResult

MAX_TIMEOUT = 300.0


class ExecuteCodeInput(BaseModel):
    code: str = Field(description="Python source code to execute")
    timeout: float = Field(default=30.0, description=f"Timeout in seconds (max {MAX_TIMEOUT})")


class ExecuteCodeTool(Tool):
    name = "execute_code"
    description = (
        "Execute a short Python script. Use for computations, data munging, "
        "and multi-step logic. Runs locally — treat it as trusted code."
    )
    input_model = ExecuteCodeInput
    requires_permission = True

    async def run(self, input: ExecuteCodeInput, ctx: ToolContext) -> ToolResult:
        timeout = min(input.timeout, MAX_TIMEOUT)
        popen_kwargs: dict = {}
        if IS_WINDOWS:
            popen_kwargs["creationflags"] = windows_hide_flags()
        try:
            proc = await asyncio.to_thread(
                self._run_bounded,
                input.code,
                str(ctx.workdir),
                timeout,
                popen_kwargs,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                content=f"Script timed out after {timeout}s", is_error=True
            )
        except Exception as e:
            return ToolResult(
                content=f"Error executing code: {type(e).__name__}: {e}",
                is_error=True,
            )
        out = (proc.stdout or b"").decode("utf-8", errors="replace")
        err = (proc.stderr or b"").decode("utf-8", errors="replace")
        content = out if not err else f"{out}\n[stderr]\n{err}"
        return ToolResult(content=content, is_error=(proc.returncode != 0))

    @staticmethod
    def _run_bounded(
        code: str,
        cwd: str,
        timeout: float,
        popen_kwargs: dict,
    ) -> subprocess.CompletedProcess:
        """Bounded run: explicit communicate(timeout) + tree-kill, so a
        child holding the captured pipes can't hang the reader threads."""
        proc = subprocess.Popen(
            [os.environ.get("EACCODE_PYTHON", "python"), "-c", code],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
