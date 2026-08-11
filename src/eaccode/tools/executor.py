"""ToolExecutor (Task 3.7) — central dispatch with Pydantic validation.

Converts tool failures into LLM-friendly text so the agent can self-correct.
"""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from eaccode.tools.base import ToolContext, ToolRegistry, ToolResult

MAX_OUTPUT_CHARS = 50_000
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def cap_output(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    """Truncate tool output to protect the context window (Phase A.3)."""
    if len(text) <= max_chars:
        return text
    head = text[: max_chars * 3 // 4]
    tail = text[-max_chars // 4 :]
    return f"{head}\n[...truncated {len(text) - max_chars} chars...]\n{tail}"


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
            result = await tool.run(input_model, context)
        except Exception as e:
            result = ToolResult(
                content=f"Error executing {name}: {type(e).__name__}: {e}",
                is_error=True,
            )
        # Secret redaction (Phase A.2): credential-like strings must never
        # enter the conversation context (and from there, session logs).
        from eaccode.security.redact import redact_secrets

        if result.content:
            result.content = redact_secrets(result.content)
        # ANSI strip + output cap (Phase A.3): keep the context window safe
        if result.content:
            result.content = cap_output(strip_ansi(result.content))
        return result

    async def execute_parallel(
        self,
        tasks: list[tuple[str, dict]],
        workdir: Path,
        *,
        ctx: ToolContext | None = None,
    ) -> list[ToolResult]:
        """G.8: dispatch independent tool calls concurrently.

        Failures are captured per call (one broken tool does not drop the
        others). The permission gate is NOT applied here — callers decide
        beforehand (the loop stays sequential by default because its
        permission modal flow is single-ask at a time).
        """
        import asyncio

        return list(
            await asyncio.gather(
                *(self.execute(name, args, workdir, ctx=ctx)
                  for name, args in tasks)
            )
        )
