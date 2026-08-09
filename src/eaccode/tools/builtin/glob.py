"""Glob tool (Task 3.6) — find files by pattern."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


class GlobInput(BaseModel):
    pattern: str = Field(description="Glob pattern, e.g. '**/*.py'")
    path: str | None = Field(
        default=None, description="Directory to search (default: workdir)"
    )


class GlobTool(Tool):
    name = "glob"
    tool_class = ToolClass.IDEMPOTENT
    description = "Find files matching a glob pattern. Returns matching paths."
    input_model = GlobInput
    requires_permission = False

    async def run(self, input: GlobInput, ctx: ToolContext) -> ToolResult:
        base = Path(input.path) if input.path else ctx.workdir
        if not base.is_absolute():
            base = ctx.workdir / base
        matches = sorted(
            str(p.relative_to(ctx.workdir)) if p.is_relative_to(ctx.workdir) else str(p)
            for p in base.glob(input.pattern)
            if p.is_file()
        )
        if not matches:
            return ToolResult(content="No files found matching the pattern.")
        return ToolResult(content="\n".join(matches))
