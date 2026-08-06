"""ToolExecutor (Task 3.7) — central dispatch with Pydantic validation.

Converts tool failures into LLM-friendly text so the agent can self-correct.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from eaccode.tools.base import ToolContext, ToolRegistry, ToolResult


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute(
        self, name: str, arguments: dict, workdir: Path, *, ctx: ToolContext | None = None
    ) -> ToolResult:
        try:
            tool = self.registry.get(name)
        except KeyError:
            available = ", ".join(t.name for t in self.registry.list())
            return ToolResult(
                content=f"Error: unknown tool '{name}'. Available tools: {available}",
                is_error=True,
            )
        try:
            input_model = tool.input_model(**arguments)
        except ValidationError as e:
            return ToolResult(
                content=f"Error: invalid arguments for {name}:\n{e}", is_error=True
            )
        context = ctx or ToolContext(workdir=workdir)
        try:
            return await tool.run(input_model, context)
        except Exception as e:
            return ToolResult(
                content=f"Error executing {name}: {type(e).__name__}: {e}",
                is_error=True,
            )
