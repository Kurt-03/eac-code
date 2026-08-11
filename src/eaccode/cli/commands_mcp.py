"""CLI sub-commands — registered onto the main click group on import."""
from __future__ import annotations

import click

from eaccode.cli import main
from eaccode.cli._output import print_error, print_info, print_success
from eaccode.config.paths import EaccodePaths

# ---------------------------------------------------------------------- mcp

@main.group()
def mcp() -> None:
    """Manage MCP servers (external tool servers)."""


@mcp.command("list")
def mcp_list() -> None:
    """List configured MCP servers."""
    from eaccode.tools.mcp.client import load_mcp_configs

    paths = EaccodePaths()
    configs = load_mcp_configs(paths.config_dir / "mcp.yaml")
    if not configs:
        print_info(
            "No MCP servers configured. Add one with: "
            "eaccode mcp add <name> -- <command> [args...]"
        )
        return
    for c in configs:
        print_info(f"  {c.name:20s} {c.command} {' '.join(c.args)}")


@mcp.command("add")
@click.argument("name")
@click.argument("command_args", nargs=-1, required=True)
def mcp_add(name: str, command_args: tuple[str, ...]) -> None:
    """Add an MCP server: eaccode mcp add <name> -- <command> [args...]"""
    from eaccode.tools.mcp.client import (
        MCPServerConfig,
        load_mcp_configs,
        save_mcp_configs,
    )

    paths = EaccodePaths()
    if "--" in command_args:
        idx = command_args.index("--")
        command = command_args[idx + 1]
        args = list(command_args[idx + 2 :])
    else:
        command = command_args[0]
        args = list(command_args[1:])
    configs = load_mcp_configs(paths.config_dir / "mcp.yaml")
    configs = [c for c in configs if c.name != name]
    configs.append(MCPServerConfig(name=name, command=command, args=args))
    save_mcp_configs(paths.config_dir / "mcp.yaml", configs)
    print_success(f"✓ MCP server '{name}' added ({command} {' '.join(args)})")


@mcp.command("remove")
@click.argument("name")
def mcp_remove(name: str) -> None:
    """Remove an MCP server."""
    from eaccode.tools.mcp.client import load_mcp_configs, save_mcp_configs

    paths = EaccodePaths()
    configs = load_mcp_configs(paths.config_dir / "mcp.yaml")
    remaining = [c for c in configs if c.name != name]
    if len(remaining) == len(configs):
        print_error(f"✗ MCP server '{name}' not found.")
        raise SystemExit(1)
    save_mcp_configs(paths.config_dir / "mcp.yaml", remaining)
    print_success(f"✓ MCP server '{name}' removed")


