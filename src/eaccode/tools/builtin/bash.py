"""Bash tool (Task 3.5) — execute shell commands with timeout + exit codes."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

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
        try:
            proc = await asyncio.create_subprocess_shell(
                input.command,
                cwd=str(ctx.workdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **ctx.env},
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                return ToolResult(
                    content=f"Command timed out after {timeout}s",
                    is_error=True,
                    metadata={"exit_code": -1, "timed_out": True},
                )
            exit_code = proc.returncode
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            content = f"$ {input.command}\n{stdout_str}"
            if stderr_str:
                content += f"\n[stderr]\n{stderr_str}"
            return ToolResult(
                content=content,
                is_error=(exit_code != 0),
                metadata={
                    "exit_code": exit_code,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                },
            )
        except Exception as e:
            return ToolResult(content=f"Error executing command: {e}", is_error=True)
