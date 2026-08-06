"""Default tool registry factory — one place to wire all built-in tools."""
from __future__ import annotations

from eaccode.tools.base import Tool, ToolRegistry
from eaccode.tools.builtin.bash import BashTool
from eaccode.tools.builtin.edit import EditTool
from eaccode.tools.builtin.glob import GlobTool
from eaccode.tools.builtin.read import ReadTool
from eaccode.tools.builtin.todo import TodoWriteTool
from eaccode.tools.builtin.write import WriteTool


def _all_tools() -> list[Tool]:
    return [
        ReadTool(),
        WriteTool(),
        EditTool(),
        BashTool(),
        GlobTool(),
        TodoWriteTool(),
    ]


def build_default_registry(allowed_tools: list[str] | None = None) -> ToolRegistry:
    """Registry with all built-in tools, optionally filtered by whitelist."""
    reg = ToolRegistry()
    tools = _all_tools()
    if allowed_tools is not None:
        allowed = set(allowed_tools)
        tools = [t for t in tools if t.name in allowed]
    for tool in tools:
        reg.register(tool)
    return reg
