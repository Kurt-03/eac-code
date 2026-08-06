"""MCP tool adapter (Task 8.1) — wrap MCP tools into the eaccode Tool protocol."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, create_model

from eaccode.tools.base import Tool, ToolContext, ToolResult


def _model_from_schema(name: str, schema: dict) -> type[BaseModel]:
    """Build a Pydantic model from a JSON schema (properties → fields)."""
    fields: dict[str, Any] = {}
    for prop_name, prop in schema.get("properties", {}).items():
        fields[prop_name] = (
            Any,
            Field(default=None, description=prop.get("description", "")),
        )
    required = set(schema.get("required", []))
    for prop_name in required:
        if prop_name in fields:
            field_info = fields[prop_name][1]
            field_info.default = ...  # required → no default (must be provided)
    return create_model(name, **fields, __validators__={})  # type: ignore[call-arg]


def create_mcp_tool(manager, server: str, tool_schema: dict) -> Tool:
    """Create a Tool that forwards calls to an MCP server tool."""
    raw_name = tool_schema["name"]
    model = _model_from_schema(f"MCP{raw_name.title()}Input", tool_schema["input_schema"])

    class MCPTool(Tool):
        name = f"mcp__{server}__{raw_name}"
        description = tool_schema.get("description", "")
        input_model = model
        requires_permission = True  # external tool servers are gated

        async def run(self, input: BaseModel, ctx: ToolContext) -> ToolResult:
            try:
                content = await manager.call_tool(
                    server, raw_name, input.model_dump(exclude_none=True)
                )
                return ToolResult(content=content or "(empty result)")
            except Exception as e:
                return ToolResult(
                    content=f"MCP error ({server}/{raw_name}): {e}", is_error=True
                )

    return MCPTool()
