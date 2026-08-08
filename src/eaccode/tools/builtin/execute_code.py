"""execute_code tool (Phase C.2) — run Python in a worker thread.

Not a true sandbox (like Hermes' execute_code it runs locally), so the
tool description tells the model to keep it to trusted computations.
Runs via subprocess in a thread — reliable on Windows, DEVNULL stdin,
5-minute cap.
"""
from __future__ import annotations

import asyncio
import subprocess

from pydantic import BaseModel, Field

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
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                ["python", "-c", input.code],
                cwd=str(ctx.workdir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
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
