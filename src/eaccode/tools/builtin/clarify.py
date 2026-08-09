"""Clarify tool (Phase C.1) — the agent asks the user instead of guessing.

Headless semantics: the question is returned to the agent with the
instruction to answer it directly, so in the REPL the user sees a clear
question in the final response.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


class ClarifyInput(BaseModel):
    question: str = Field(description="The question to ask the user")


class ClarifyTool(Tool):
    name = "clarify"
    tool_class = ToolClass.IDEMPOTENT
    description = (
        "Ask the user a clarifying question when the task is ambiguous. "
        "Call this instead of guessing when requirements are unclear."
    )
    input_model = ClarifyInput
    requires_permission = False

    async def run(self, input: ClarifyInput, ctx: ToolContext) -> ToolResult:
        return ToolResult(
            content=(
                f"Clarification requested: {input.question}\n"
                "Answer this question in your final response — the user "
                "will read it and reply."
            )
        )
