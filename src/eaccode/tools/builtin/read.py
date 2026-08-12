"""Read tool (Task 3.2) — read files with offset/limit, line-numbered."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


class ReadInput(BaseModel):
    path: str = Field(description="Absolute path or path relative to workdir")
    offset: int | None = Field(
        default=None, description="Line number to start from (1-indexed)"
    )
    limit: int | None = Field(
        default=None, description="Max number of lines to read"
    )


class ReadTool(Tool):
    name = "read"
    tool_class = ToolClass.IDEMPOTENT
    description = (
        "Read a file's contents. Supports offset/limit for large files. "
        "Returns lines with line numbers."
    )
    input_model = ReadInput
    requires_permission = False

    async def run(self, input: ReadInput, ctx: ToolContext) -> ToolResult:
        from eaccode.tools.safety import read_blocked_error

        path = Path(input.path)
        if not path.is_absolute():
            path = ctx.workdir / path
        blocked = read_blocked_error(path)
        if blocked:
            return ToolResult(content=blocked, is_error=True)
        if not path.exists():
            return ToolResult(content=f"Error: file not found: {path}", is_error=True)
        try:
            import asyncio

            # C6 (audit): file I/O must not block the Textual event loop.
            text = await asyncio.to_thread(
                path.read_text, encoding="utf-8", errors="replace"
            )
        except Exception as e:
            return ToolResult(content=f"Error reading file: {e}", is_error=True)
        lines = text.splitlines()
        start = max((input.offset or 1) - 1, 0)
        end = start + input.limit if input.limit else len(lines)
        numbered = [
            f"{i + 1:6}\t{line}" for i, line in enumerate(lines[start:end], start=start)
        ]
        return ToolResult(
            content="\n".join(numbered),
            metadata={"path": str(path), "total_lines": len(lines)},
        )
