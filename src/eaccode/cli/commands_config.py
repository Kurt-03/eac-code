"""CLI sub-commands — registered onto the main click group on import."""
from __future__ import annotations

from pathlib import Path

import click

from eaccode.cli import main
from eaccode.cli._output import print_error, print_info, print_success, print_warn
from eaccode.config.paths import EaccodePaths
from eaccode.config.providers import load_providers
from eaccode.config.settings import PermissionMode, Settings

# ------------------------------------------------------------------ config

@main.group()
def config() -> None:
    """Show and change settings."""


@config.command("show")
def config_show() -> None:
    """Show current settings."""
    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    for k, v in settings.model_dump(mode="json").items():
        print_info(f"  {k:24s} {v}")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a setting, e.g. `eaccode config set permission_mode acceptEdits`."""
    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    if key not in Settings.model_fields:
        print_error(f"✗ Unknown setting: {key}. Known: {', '.join(Settings.model_fields)}")
        raise SystemExit(1) from None
    # Pydantic validates itself (enum, int, bool, float, constraints like ge=1)
    try:
        updated = Settings.model_validate({**settings.model_dump(), key: value})
    except Exception as e:
        print_error(f"✗ Invalid value for {key}: {value} ({e})")
        raise SystemExit(1) from None
    updated.save(paths.settings_file)
    value_out = getattr(updated, key)
    print_success(f"✓ {key} = {value_out.value if hasattr(value_out, 'value') else value_out}")


@main.command("run")
@click.argument("prompt")
@click.option("--print", "print_mode", is_flag=True, help="Headless: result to stdout, no TUI")
@click.option("--output-format", default="text", type=click.Choice(["text", "json"]),
              help="Output format (headless)")
@click.option("--max-turns", default=None, type=int, help="Override max turns")
@click.option("--allowed-tools", default=None, help="Comma-separated tool whitelist")
@click.option("--mode", "mode_name", default=None,
              type=click.Choice([m.value for m in PermissionMode]),
              help="Permission mode override (default for headless runs: bypassPermissions)")
@click.option("--model", default=None, help="Model alias or provider/model")
def run_cmd(prompt: str, print_mode: bool, output_format: str, max_turns: int | None,
            allowed_tools: str | None, mode_name: str | None, model: str | None) -> None:
    """Run one task headlessly (for CI, the queue, and the future GUI)."""
    import asyncio
    import json as jsonlib

    from eaccode.agent.factory import build_agent
    from eaccode.agent.loop import MaxTurnsExceededError
    from eaccode.llm.models import Message

    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    if not load_providers(paths.providers_file):
        print_info(
            "No providers configured. Add one first:\n"
            "  eaccode providers add --provider minimax --model MiniMax-M3"
        )
        raise SystemExit(1)

    # Headless runs are non-interactive: permission prompts would hang or
    # auto-deny. Default to bypassPermissions (like `claude -p` in CI);
    # an explicit --mode override wins. The --allowed-tools whitelist
    # remains the safety net.
    mode = (
        PermissionMode(mode_name)
        if mode_name
        else PermissionMode.BYPASS_PERMISSIONS
    )
    # Load MCP servers (optional; failures degrade to a warning)
    mcp_tools: list = []
    try:
        import asyncio as _asyncio

        from eaccode.tools.mcp.client import connect_mcp_tools

        mcp_tools, _ = _asyncio.run(connect_mcp_tools(paths.config_dir / "mcp.yaml"))
    except Exception as e:
        print_warn(f"Warning: MCP servers failed to load: {e}")

    agent, _, _ = build_agent(
        Path.cwd(),
        mode=mode,
        max_turns=max_turns,
        allowed_tools=allowed_tools.split(",") if allowed_tools else None,
        model=model,
        settings=settings,
        paths=paths,
        mcp_tools=mcp_tools,
    )

    try:
        result = asyncio.run(agent.run([Message.user(prompt)]))
    except MaxTurnsExceededError as e:
        print_error(f"Error: {e}")
        raise SystemExit(1) from None

    if output_format == "json":
        print_info(jsonlib.dumps({
            "result": result.final_text,
            "turns": result.turns,
            "cost_usd": round(result.cost_usd, 4),
            "usage": {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
        }))
    else:
        print_info(result.final_text)


