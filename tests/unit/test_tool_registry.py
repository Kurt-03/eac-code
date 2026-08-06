"""Tests für Tool-Protocol + Registry (Task 3.1)."""
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolContext, ToolRegistry, ToolResult
from eaccode.tools.schema import to_json_schema


class EchoInput(BaseModel):
    text: str = Field(description="Text to echo back")


class EchoTool(Tool):
    name = "echo"
    description = "Echoes the input back."
    input_model = EchoInput

    async def run(self, input: EchoInput, ctx: ToolContext) -> ToolResult:
        return ToolResult(content=input.text)


@pytest.mark.asyncio
async def test_tool_execution():
    tool = EchoTool()
    ctx = ToolContext(workdir=Path("/tmp"))
    result = await tool.run(EchoInput(text="hi"), ctx)
    assert result.content == "hi"


@pytest.mark.asyncio
async def test_tool_registry_lookup():
    reg = ToolRegistry()
    reg.register(EchoTool())
    schema = reg.get_schema("echo")
    assert schema["name"] == "echo"
    assert "text" in schema["input_schema"]["properties"]


def test_pydantic_to_json_schema():
    schema = to_json_schema(EchoInput)
    assert schema["type"] == "object"
    assert "text" in schema["properties"]
    assert "description" in schema["properties"]["text"]


def test_registry_schemas_export():
    reg = ToolRegistry()
    reg.register(EchoTool())
    schemas = reg.schemas()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "echo"
    assert schemas[0]["description"] == "Echoes the input back."


def test_unknown_tool_raises_keyerror():
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        reg.get("gibt-es-nicht")


def test_tool_default_requires_permission():
    assert EchoTool().requires_permission is True  # Default: gefährliche Tools fragen
