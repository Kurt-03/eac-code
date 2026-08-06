"""CLI entry point (Task 1.4).

Command hierarchy (see plan, section "CLI Command Tree"):
    eaccode                     → REPL (Phase 7, currently a hint)
    eaccode paths               → show XDG paths
    eaccode providers add/list/remove/set-default
    eaccode config show/set     → show/change settings
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from eaccode.config.paths import EaccodePaths
from eaccode.config.providers import ProviderConfig, load_providers, save_providers
from eaccode.config.settings import PermissionMode, Settings


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0", prog_name="eaccode")
@click.pass_context
def main(ctx: click.Context) -> None:
    """eaccode — autonomous coding agent (BYOK)."""
    if ctx.invoked_subcommand is None:
        if not sys.stdin.isatty():
            click.echo(
                "REPL requires an interactive terminal. "
                "Use: eaccode run <prompt> (headless)"
            )
            return
        from eaccode.ui.repl import run_repl

        run_repl()


@main.command()
def paths() -> None:
    """Show resolved config/data paths."""
    p = EaccodePaths()
    click.echo(f"config:    {p.config_dir}")
    click.echo(f"data:      {p.data_dir}")
    click.echo(f"cache:     {p.cache_dir}")
    click.echo(f"sessions:  {p.sessions_dir}")
    click.echo(f"memory:    {p.memory_dir}")
    click.echo(f"skills:    {p.skills_dir}")


# ---------------------------------------------------------------- providers

@main.group()
def providers() -> None:
    """Manage BYOK providers."""


@providers.command("add")
@click.option("--provider", required=True,
              help="Provider name (minimax, anthropic, opencode-go, ...)")
@click.option("--model", required=True, help="Default model for this provider")
@click.option("--api-key", prompt=True, hide_input=True, help="API key (prompted hidden)")
@click.option("--base-url", default=None, help="Custom API base URL (OpenAI-compatible endpoints)")
def providers_add(provider: str, model: str, api_key: str, base_url: str | None) -> None:
    """Add a provider + API key (BYOK)."""
    paths = EaccodePaths()
    existing = load_providers(paths.providers_file)
    for p in existing:
        if p.name == provider:
            click.echo(
                f"✗ Provider '{provider}' already exists — remove it first "
                f"or edit {paths.providers_file} directly."
            )
            raise SystemExit(1)
    existing.append(
        ProviderConfig(name=provider, api_key=api_key, model=model, base_url=base_url)  # type: ignore[arg-type]
    )
    save_providers(existing, paths.providers_file)
    paths.providers_file.chmod(0o600)
    click.echo(f"✓ {provider} → {model} saved ({paths.providers_file})")


@providers.command("list")
def providers_list() -> None:
    """List configured providers (keys masked)."""
    paths = EaccodePaths()
    providers_list = load_providers(paths.providers_file)
    if not providers_list:
        click.echo("No providers configured. Add one with: eaccode providers add")
        return
    for p in providers_list:
        key = p.api_key.get_secret_value()
        masked = f"{key[:4]}…{key[-2:]}" if len(key) > 6 else "***"
        suffix = f" (base_url: {p.base_url})" if p.base_url else ""
        click.echo(f"  {p.name:14s} {p.model:30s} key={masked}{suffix}")


@providers.command("remove")
@click.argument("name")
def providers_remove(name: str) -> None:
    """Remove a provider."""
    paths = EaccodePaths()
    existing = load_providers(paths.providers_file)
    remaining = [p for p in existing if p.name != name]
    if len(remaining) == len(existing):
        click.echo(f"✗ Provider '{name}' not found.")
        raise SystemExit(1)
    save_providers(remaining, paths.providers_file)
    click.echo(f"✓ {name} removed")


@providers.command("set-default")
@click.argument("name")
def providers_set_default(name: str) -> None:
    """Set the default provider for new sessions."""
    paths = EaccodePaths()
    if not any(p.name == name for p in load_providers(paths.providers_file)):
        click.echo(f"✗ Provider '{name}' not configured.")
        raise SystemExit(1)
    settings = Settings.load(paths.settings_file)
    settings.default_provider = name
    settings.save(paths.settings_file)
    click.echo(f"✓ Default provider: {name}")


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
        click.echo(f"  {k:24s} {v}")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a setting, e.g. `eaccode config set permission_mode acceptEdits`."""
    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    if key not in Settings.model_fields:
        click.echo(f"✗ Unknown setting: {key}. Known: {', '.join(Settings.model_fields)}")
        raise SystemExit(1) from None
    # Pydantic validates itself (enum, int, bool, float, constraints like ge=1)
    try:
        updated = Settings.model_validate({**settings.model_dump(), key: value})
    except Exception as e:
        click.echo(f"✗ Invalid value for {key}: {value} ({e})")
        raise SystemExit(1) from None
    updated.save(paths.settings_file)
    value_out = getattr(updated, key)
    click.echo(f"✓ {key} = {value_out.value if hasattr(value_out, 'value') else value_out}")


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
    from eaccode.config.providers import load_providers
    from eaccode.llm.models import Message

    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    if not load_providers(paths.providers_file):
        click.echo(
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
    agent, _, _ = build_agent(
        Path.cwd(),
        mode=mode,
        max_turns=max_turns,
        allowed_tools=allowed_tools.split(",") if allowed_tools else None,
        model=model,
        settings=settings,
        paths=paths,
    )

    try:
        result = asyncio.run(agent.run([Message.user(prompt)]))
    except MaxTurnsExceededError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from None

    if output_format == "json":
        click.echo(jsonlib.dumps({
            "result": result.final_text,
            "turns": result.turns,
            "cost_usd": round(result.cost_usd, 4),
            "usage": {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
        }))
    else:
        click.echo(result.final_text)


if __name__ == "__main__":
    main()
