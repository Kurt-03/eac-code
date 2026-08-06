"""TodoWrite tool (Task 3.6) — in-memory task tracking for the agent."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolContext, ToolResult


class TodoItem(BaseModel):
    status: Literal["pending", "in_progress", "completed", "cancelled"] = "pending"
    content: str = Field(description="What needs to be done")
    activeForm: str | None = Field(
        default=None, description="Active verb form, e.g. 'Fixing auth'"
    )


class TodoWriteInput(BaseModel):
    todos: list[TodoItem] = Field(description="Full list of todos to track")


class TodoWriteTool(Tool):
    name = "todo_write"
    description = (
        "Track progress on a multi-step task. Always maintain the full list "
        "of remaining work in every call."
    )
    input_model = TodoWriteInput
    requires_permission = False

    async def run(self, input: TodoWriteInput, ctx: ToolContext) -> ToolResult:
        lines = []
        icons = {
            "pending": "⏳",
            "in_progress": "▶",
            "completed": "✓",
            "cancelled": "✗",
        }
        for t in input.todos:
            lines.append(f"{icons.get(t.status, '?')} {t.content}")
        return ToolResult(
            content="\n".join(lines) if lines else "No todos.",
            metadata={"count": len(input.todos)},
        )
