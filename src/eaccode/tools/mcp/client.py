"""MCP client (Task 8.1) — stdio servers from mcp.yaml, tool schemas, calls."""
from __future__ import annotations

import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


def load_mcp_configs(path: Path) -> list[MCPServerConfig]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [MCPServerConfig(**s) for s in raw.get("mcp_servers", [])]


def save_mcp_configs(path: Path, configs: list[MCPServerConfig]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "mcp_servers": [
            {**{"name": c.name, "command": c.command, "args": c.args},
             **({"env": c.env} if c.env else {})}
            for c in configs
        ]
    }
    path.write_text(yaml.safe_dump(data, default_flow_style=False, allow_unicode=True),
                    encoding="utf-8")


async def connect_mcp_tools(config_path: Path) -> tuple[list[Tool], MCPManager | None]:
    """Load mcp.yaml and connect. Returns (tools, manager) or ([], None)."""
    from eaccode.tools.mcp.adapter import create_mcp_tool

    configs = load_mcp_configs(config_path)
    if not configs:
        return [], None
    mgr = MCPManager()
    await mgr.connect(configs)
    tools = [
        create_mcp_tool(mgr, server, schema)
        for server, schemas in mgr._tools_by_server.items()
        for schema in schemas
    ]
    return tools, mgr


class MCPManager:
    """Owns stdio sessions to MCP servers; exposes their tools as schemas."""

    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._tools_by_server: dict[str, list[dict]] = {}

    async def connect(self, configs: list[MCPServerConfig]) -> None:
        for cfg in configs:
            env = {**os.environ, **({k: os.path.expandvars(v) for k, v in (cfg.env or {}).items()})}
            params = StdioServerParameters(command=cfg.command, args=cfg.args, env=env)
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._sessions[cfg.name] = session
            result = await session.list_tools()
            self._tools_by_server[cfg.name] = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.input_schema,
                }
                for t in result.tools
            ]

    async def call_tool(self, server: str, tool: str, arguments: dict) -> str:
        session = self._sessions[server]
        result = await session.call_tool(tool, arguments=arguments)
        return "\n".join(
            c.text for c in result.content if hasattr(c, "text") and c.text
        )

    def all_tool_schemas(self) -> list[dict]:
        schemas = []
        for server, tools in self._tools_by_server.items():
            for t in tools:
                schemas.append({**t, "name": f"mcp__{server}__{t['name']}"})
        return schemas

    async def shutdown(self) -> None:
        await self._stack.aclose()
