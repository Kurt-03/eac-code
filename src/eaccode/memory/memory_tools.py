"""Memory tools (P0.3) — the agent-facing surface of the markdown memory.

Fills the gap the toolset registry already declared: memory_remember /
memory_recall / memory_forget (+ memory_edit). The tools operate on the
user-facing markdown files (MEMORY.md project-scoped, USER.md / SOUL.md
global) with hard char budgets. Writes go through the permission system
(requires_permission=True) — memory edits are state changes the user
should see; reads are free.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from eaccode.memory.markdown_store import (
    BudgetExceededError,
    MarkdownMemoryStore,
)
from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


def _store(ctx: ToolContext) -> MarkdownMemoryStore:
    from eaccode.config.paths import EaccodePaths

    memory_dir = ctx.memory_dir or EaccodePaths().memory_dir
    return MarkdownMemoryStore(memory_dir)


def _project_hash(ctx: ToolContext) -> str:
    from eaccode.memory.store import MemoryStore

    return MemoryStore.project_hash(ctx.workdir)


class MemoryRememberInput(BaseModel):
    fact: str = Field(description="Short fact to remember (project memory)")


class MemoryRememberTool(Tool):
    name = "memory_remember"
    description = (
        "Save a short project fact to MEMORY.md (char budget 2200). "
        "Use for durable lessons and conventions."
    )
    input_model = MemoryRememberInput
    requires_permission = True

    async def run(self, input: MemoryRememberInput, ctx: ToolContext) -> ToolResult:
        try:
            _store(ctx).add_fact("memory", input.fact, _project_hash(ctx))
        except BudgetExceededError as e:
            return ToolResult(content=str(e), is_error=True)
        return ToolResult(content=f"Remembered: {input.fact.strip()}")


class MemoryForgetInput(BaseModel):
    needle: str = Field(description="Text identifying the fact line to remove")


class MemoryForgetTool(Tool):
    name = "memory_forget"
    description = "Remove a fact line containing the given text from MEMORY.md."
    input_model = MemoryForgetInput
    requires_permission = True

    async def run(self, input: MemoryForgetInput, ctx: ToolContext) -> ToolResult:
        removed = _store(ctx).remove_line("memory", input.needle, _project_hash(ctx))
        if not removed:
            return ToolResult(
                content=f"No memory line contains {input.needle!r}",
                is_error=True,
            )
        return ToolResult(content=f"Forgot: {input.needle}")


class MemoryEditInput(BaseModel):
    old: str = Field(description="Text in the line to replace")
    new: str = Field(description="Replacement fact text")


class MemoryEditTool(Tool):
    name = "memory_edit"
    description = "Replace a MEMORY.md fact line containing `old` with `new`."
    input_model = MemoryEditInput
    requires_permission = True

    async def run(self, input: MemoryEditInput, ctx: ToolContext) -> ToolResult:
        try:
            replaced = _store(ctx).replace_fact(
                "memory", input.old, input.new, _project_hash(ctx)
            )
        except BudgetExceededError as e:
            return ToolResult(content=str(e), is_error=True)
        if not replaced:
            return ToolResult(
                content=f"No memory line contains {input.old!r}",
                is_error=True,
            )
        return ToolResult(content=f"Updated: {input.new.strip()}")


class MemoryRecallInput(BaseModel):
    scope: str = Field(
        default="memory",
        description="memory (project MEMORY.md) | user (USER.md) | soul (SOUL.md)",
    )


class MemoryRecallTool(Tool):
    name = "memory_recall"
    tool_class = ToolClass.IDEMPOTENT
    description = (
        "Read the stored memory: project facts (memory), user profile "
        "(user), or working style (soul)."
    )
    input_model = MemoryRecallInput
    requires_permission = False

    async def run(self, input: MemoryRecallInput, ctx: ToolContext) -> ToolResult:
        scope = input.scope.lower()
        if scope not in ("memory", "user", "soul"):
            return ToolResult(
                content="scope must be memory | user | soul", is_error=True
            )
        if scope == "memory":
            text = _store(ctx).read("memory", _project_hash(ctx))
        else:
            text = _store(ctx).read(scope)
        if not text.strip():
            return ToolResult(content=f"No {scope.upper()} content yet.")
        return ToolResult(content=text.strip())
