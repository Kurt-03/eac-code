"""Tests for the MCP client + tool adapter (Task 8.1)."""
import sys
from pathlib import Path

import pytest

from eaccode.tools.mcp.adapter import create_mcp_tool
from eaccode.tools.mcp.client import MCPManager, MCPServerConfig


@pytest.fixture
def echo_server_config() -> MCPServerConfig:
    server_script = Path(__file__).parent.parent / "fixtures" / "mcp_echo_server.py"
    return MCPServerConfig(
        name="echo-server",
        command=sys.executable,
        args=[str(server_script)],
    )


@pytest.mark.asyncio
async def test_mcp_connect_lists_tools(echo_server_config):
    mgr = MCPManager()
    await mgr.connect([echo_server_config])
    try:
        schemas = mgr.all_tool_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "mcp__echo-server__echo"
        assert schemas[0]["description"] == "Echo the input back"
        assert "text" in schemas[0]["input_schema"]["properties"]
    finally:
        await mgr.shutdown()


@pytest.mark.asyncio
async def test_mcp_call_tool(echo_server_config):
    mgr = MCPManager()
    await mgr.connect([echo_server_config])
    try:
        result = await mgr.call_tool("echo-server", "echo", {"text": "hallo"})
        assert "echo:hallo" in result
    finally:
        await mgr.shutdown()


@pytest.mark.asyncio
async def test_mcp_adapter_executes_tool(echo_server_config):
    mgr = MCPManager()
    await mgr.connect([echo_server_config])
    try:
        schema = mgr.all_tool_schemas()[0]
        tool = create_mcp_tool(mgr, "echo-server", schema)
        from eaccode.tools.base import ToolContext

        ctx = ToolContext(workdir=Path("/tmp"))
        result = await tool.run(tool.input_model(text="adapter-test"), ctx)
        assert result.is_error is False
        assert "echo:adapter-test" in result.content
    finally:
        await mgr.shutdown()
