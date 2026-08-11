"""Tool protocol and registry (Task 3.1)."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from eaccode.tools.schema import to_json_schema


class ToolClass(str, enum.Enum):  # noqa: UP042  (str values for config/schema)
    """Tool classification for the loop guardrails (Phase C.1).

    Mirrors Hermes' ``agent/tool_guardrails.py`` taxonomy:
    - IDEMPOTENT: read-style, safe to repeat (read, glob, grep, web_fetch,
      session_search). Repeating the same call with the same result is a
      no-progress signal.
    - MUTATING: write-style, changes state (write, edit, bash, todo,
      skill_create, delegate_task). Repeated identical failures are the
      loop signal.
    - RUNAWAY: per-turn caps apply (web_search, delegate_task) — a single
      turn spiraling into dozens of searches/subagents is pathological.
    """

    IDEMPOTENT = "idempotent"
    MUTATING = "mutating"
    RUNAWAY = "runaway"


class ToolContext(BaseModel):
    workdir: Path
    env: dict[str, str] = Field(default_factory=dict)
    permission_mode: str = "default"
    skills_dir: Path = Field(default_factory=Path)
    # P0.3: markdown memory dir (None → tools fall back to EaccodePaths).
    memory_dir: Path | None = None
    config: Any = None


class ToolResult(BaseModel):
    content: str
    is_error: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Tool(ABC):
    # Not ClassVar: plugin tools (context_engine, Phase I.12) set these
    # per-instance, so the annotations must allow instance assignment.
    name: str
    description: str
    input_model: type[BaseModel]
    requires_permission: bool = True
    # Phase C.1: loop-guardrail classification (default: mutating — the
    # safe assumption; read-style tools override to idempotent).
    tool_class: ClassVar[ToolClass] = ToolClass.MUTATING

    @abstractmethod
    async def run(self, input: BaseModel, ctx: ToolContext) -> ToolResult: ...

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": to_json_schema(self.input_model),
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict]:
        return [t.to_schema() for t in self._tools.values()]

    def get_schema(self, name: str) -> dict:
        return self._tools[name].to_schema()
