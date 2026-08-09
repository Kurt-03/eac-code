"""delegate_task tool (Phase C.3) — in-process subagent with isolated context.

The subagent is a fresh AgentLoop (own message history) built through the
same factory as the main agent; only its final text returns as the tool
result. A module-level semaphore caps concurrent subagents at 3.
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult

_semaphore = asyncio.Semaphore(3)


class DelegateInput(BaseModel):
    goal: str = Field(description="The task for the subagent (self-contained)")
    max_turns: int = Field(default=15, description="Subagent turn budget")


class DelegateTool(Tool):
    name = "delegate_task"
    description = (
        "Spawn a subagent with an isolated context to work on a focused "
        "subtask. Returns only its final answer. Use for independent "
        "research or implementation pieces."
    )
    input_model = DelegateInput
    requires_permission = True
    tool_class = ToolClass.RUNAWAY

    async def run(self, input: DelegateInput, ctx: ToolContext) -> ToolResult:
        builder = (ctx.config or {}).get("delegate_builder") or getattr(
            self, "delegate_builder", None
        )
        if not builder:
            return ToolResult(
                content="delegate_task is not available in this context.",
                is_error=True,
            )
        async with _semaphore:
            try:
                agent, _, _ = await builder(
                    ctx.workdir, max_turns=input.max_turns
                )
                from eaccode.llm.models import Message

                result = await agent.run([Message.user(input.goal)])
                return ToolResult(content=result.final_text)
            except Exception as e:
                return ToolResult(
                    content=f"Subagent failed: {type(e).__name__}: {e}",
                    is_error=True,
                )
