"""Tool-Protocol und Registry (Task 3.1)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from eaccode.tools.schema import to_json_schema


class ToolContext(BaseModel):
    workdir: Path
    env: dict[str, str] = Field(default_factory=dict)
    permission_mode: str = "default"
    skills_dir: Path = Field(default_factory=Path)
    config: Any = None


class ToolResult(BaseModel):
    content: str
    is_error: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    input_model: ClassVar[type[BaseModel]]
    requires_permission: ClassVar[bool] = True

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
