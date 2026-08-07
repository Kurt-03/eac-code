"""Bash tool (Task 3.5) — execute shell commands with timeout + exit codes.

Runs in a worker thread via asyncio.to_thread: asyncio.create_subprocess_*
is broken on Windows (errno 9 with the default Proactor loop, and NOT
implemented at all with the Selector loop), so the sync subprocess module
is the only reliable cross-platform path.
"""
from __future__ import annotations

import asyncio
import os
import subprocess

from pydantic import BaseModel, Field

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
        env = {**os.environ, **ctx.env}
        # DEVNULL: the child must never read from the terminal — in the REPL
        # that handle belongs to the UI (errno 9 / input stealing).
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                input.command,
                shell=True,
                cwd=str(ctx.workdir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=timeout,
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
