"""delegate_task tool (Phase C.3 + I.13) — subagents, single or batch.

The subagent is a fresh AgentLoop (own message history) built through the
same factory as the main agent; only its final text returns as the tool
result. A module-level semaphore caps concurrent subagents at 3.

Phase I.13: ``tasks`` — an array of parallel goals (Hermes' batch mode).
Each task spawns a subagent; results come back as one consolidated block.
The run waits for all tasks (failures are captured per-task, so one
broken goal doesn't drop the others).
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult

_semaphore = asyncio.Semaphore(3)


class DelegateTask(BaseModel):
    goal: str = Field(description="The task for the subagent (self-contained)")
    context: str = Field(default="", description="Background context for this task")


class DelegateInput(BaseModel):
    goal: str = Field(default="", description="The task for the subagent (self-contained)")
    context: str = Field(default="", description="Background information the subagent needs")
    tasks: list[DelegateTask] | None = Field(
        default=None,
        description="Batch mode: parallel tasks, each with its own goal+context. "
                    "When set, `goal` is ignored.",
    )
    max_turns: int = Field(default=15, description="Subagent turn budget")


class DelegateTool(Tool):
    name = "delegate_task"
    description = (
        "Spawn a subagent with an isolated context to work on a focused "
        "subtask. Returns only its final answer. Use for independent "
        "research or implementation pieces. Pass `tasks` as an array to "
        "run several goals in parallel (batch mode)."
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
        if input.tasks:
            return await self._run_batch(builder, input, ctx)
        return await self._run_single(builder, input.goal, input.context,
                                      input.max_turns, ctx)

    async def _run_single(self, builder, goal: str, context: str,
                          max_turns: int, ctx: ToolContext) -> ToolResult:
        async with _semaphore:
            try:
                agent, _, _ = await builder(ctx.workdir, max_turns=max_turns)
                from eaccode.llm.models import Message

                prompt = f"{context}\n\n{goal}" if context else goal
                result = await agent.run([Message.user(prompt)])
                return ToolResult(content=result.final_text)
            except Exception as e:
                return ToolResult(
                    content=f"Subagent failed: {type(e).__name__}: {e}",
                    is_error=True,
                )

    async def _run_batch(self, builder, input: DelegateInput,
                         ctx: ToolContext) -> ToolResult:
        """Phase I.13: parallel batch — one consolidated result block."""
        async def _one(task: DelegateTask) -> tuple[str, str, bool]:
            result = await self._run_single(
                builder, task.goal, task.context, input.max_turns, ctx
            )
            return task.goal, result.content, result.is_error

        try:
            results = await asyncio.gather(*[_one(t) for t in input.tasks])
        except Exception as e:
            return ToolResult(
                content=f"Batch delegation failed: {type(e).__name__}: {e}",
                is_error=True,
            )
        blocks = []
        for i, (goal, content, is_error) in enumerate(results, 1):
            status = "✗" if is_error else "✓"
            blocks.append(f"--- task {i}: {status} {goal[:80]}\n{content}")
        return ToolResult(content="\n\n".join(blocks))
