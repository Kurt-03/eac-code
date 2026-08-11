"""CLI sub-commands — registered onto the main click group on import."""
from __future__ import annotations

import click

from eaccode.cli import main
from eaccode.cli._output import print_error, print_info, print_success
from eaccode.config.paths import EaccodePaths
from eaccode.config.providers import ProviderConfig, load_providers, save_providers
from eaccode.config.settings import Settings

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
@click.option("--vision", is_flag=True, default=False,
              help="Mark this provider as vision-capable (extra: vision=true)")
def providers_add(provider: str, model: str, api_key: str, base_url: str | None,
                  vision: bool = False) -> None:
    """Add a provider + API key (BYOK)."""
    paths = EaccodePaths()
    existing = load_providers(paths.providers_file)
    for p in existing:
        if p.name == provider:
            print_error(
                f"✗ Provider '{provider}' already exists — remove it first "
                f"or edit {paths.providers_file} directly."
            )
            raise SystemExit(1)
    extra = {"vision": "true"} if vision else {}
    existing.append(
        ProviderConfig(name=provider, api_key=api_key, model=model,
                       base_url=base_url, extra=extra)  # type: ignore[arg-type]
    )
    save_providers(existing, paths.providers_file)
    paths.providers_file.chmod(0o600)
    print_success(f"✓ {provider} → {model} saved ({paths.providers_file})")


@providers.command("list")
def providers_list() -> None:
    """List configured providers (keys masked)."""
    paths = EaccodePaths()
    providers_list = load_providers(paths.providers_file)
    if not providers_list:
        print_info("No providers configured. Add one with: eaccode providers add")
        return
    for p in providers_list:
        key = p.api_key.get_secret_value()
        masked = f"{key[:4]}…{key[-2:]}" if len(key) > 6 else "***"
        suffix = f" (base_url: {p.base_url})" if p.base_url else ""
        print_info(f"  {p.name:14s} {p.model:30s} key={masked}{suffix}")


@providers.command("remove")
@click.argument("name")
def providers_remove(name: str) -> None:
    """Remove a provider."""
    paths = EaccodePaths()
    existing = load_providers(paths.providers_file)
    remaining = [p for p in existing if p.name != name]
    if len(remaining) == len(existing):
        print_error(f"✗ Provider '{name}' not found.")
        raise SystemExit(1)
    save_providers(remaining, paths.providers_file)
    print_success(f"✓ {name} removed")


@providers.command("set-default")
@click.argument("name")
def providers_set_default(name: str) -> None:
    """Set the default provider for new sessions."""
    paths = EaccodePaths()
    if not any(p.name == name for p in load_providers(paths.providers_file)):
        print_error(f"✗ Provider '{name}' not configured.")
        raise SystemExit(1)
    settings = Settings.load(paths.settings_file)
    settings.default_provider = name
    settings.save(paths.settings_file)
    print_success(f"✓ Default provider: {name}")


