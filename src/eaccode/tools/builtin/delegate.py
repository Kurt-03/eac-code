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
import time
from uuid import uuid4

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
    background: bool = Field(
        default=False,
        description="C.4: run in the background and return immediately. "
                    "The result is delivered into the next turns as context.",
    )


# C.4: in-process background delegation registry (task_id -> future).
_background_tasks: dict[int, asyncio.Task] = {}
_background_results: dict[int, str] = {}
_background_failures: dict[int, str] = {}
_next_task_id = 1


def background_status() -> dict:
    """Active/finished counts for the REPL status line."""
    return {
        "active": len([t for t in _background_tasks.values() if not t.done()]),
        "done": len(_background_results),
        "failed": len(_background_failures),
    }


def active_background_tasks() -> list[int]:
    return [tid for tid, t in _background_tasks.items() if not t.done()]


def collect_background_results() -> list[str]:
    """Finished background results (consumed once by the loop)."""
    results: list[str] = []
    for tid in sorted(_background_results):
        results.append(f"[delegation #{tid}] {_background_results[tid]}")
    _background_results.clear()
    for tid in sorted(_background_failures):
        results.append(f"[delegation #{tid} failed] {_background_failures[tid]}")
    _background_failures.clear()
    return results


def cancel_all_background() -> None:
    for task in _background_tasks.values():
        if not task.done():
            task.cancel()
    _background_tasks.clear()


class DelegateTool(Tool):
    name = "delegate_task"
    description = (
        "Spawn a subagent with an isolated context to work on a focused "
        "subtask. Returns only its final answer. Use for independent "
        "research or implementation pieces. Pass `tasks` as an array to "
        "run several goals in parallel (batch mode), or `background` to "
        "return immediately and get the result in later turns."
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
        if input.background:
            return await self._run_background(builder, input, ctx)
        return await self._run_single(builder, input.goal, input.context,
                                      input.max_turns, ctx)

    async def _run_background(self, builder, input: DelegateInput,
                              ctx: ToolContext) -> ToolResult:
        """C.4: fire-and-forget — the loop collects the result later."""
        global _next_task_id
        task_id = _next_task_id
        _next_task_id += 1

        async def _work() -> None:
            try:
                result = await self._run_single(
                    builder, input.goal, input.context, input.max_turns, ctx
                )
                if result.is_error:
                    _background_failures[task_id] = result.content
                else:
                    _background_results[task_id] = result.content
            except Exception as e:  # pragma: no cover - defensive
                _background_failures[task_id] = f"{type(e).__name__}: {e}"

        task = asyncio.create_task(_work())
        _background_tasks[task_id] = task
        task.add_done_callback(lambda _t: _background_tasks.pop(task_id, None))
        return ToolResult(
            content=(
                f"Delegated #{task_id} in the background — "
                "the result arrives in a later turn as context."
            ),
            metadata={"delegation_id": task_id},
        )

    async def _run_single(self, builder, goal: str, context: str,
                          max_turns: int, ctx: ToolContext) -> ToolResult:
        async with _semaphore:
            try:
                agent, _, _ = await builder(ctx.workdir, max_turns=max_turns)
                # P0.5: attribute this subagent's writes so the caller can
                # detect conflicts with its own edits.
                sub_id = f"sub:{uuid4().hex[:8]}"
                agent.config.writer_id = sub_id
                from eaccode.tools.file_state import writes_by

                start_ts = time.monotonic()
                from eaccode.llm.models import Message

                prompt = f"{context}\n\n{goal}" if context else goal
                result = await agent.run([Message.user(prompt)])
                wrote = writes_by(start_ts, {sub_id})
                content = result.final_text
                if wrote:
                    paths = ", ".join(p for p, _ in wrote)
                    content += (
                        f"\n\n[file-state] Subagent wrote: {paths} — "
                        "check for conflicts with your own edits."
                    )
                return ToolResult(content=content)
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
            results = await asyncio.gather(*[_one(t) for t in (input.tasks or [])])
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
