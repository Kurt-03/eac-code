"""CLI-Einstiegspunkt (Task 1.4).

Befehlshierarchie (siehe Plan, Abschnitt "CLI Command Tree"):
    eaccode                     → REPL (Phase 7, aktuell Hinweis)
    eaccode paths               → XDG-Pfade anzeigen
    eaccode providers add/list/remove/set-default
    eaccode config show/set     → Settings anzeigen/ändern
"""
from __future__ import annotations

import click

from eaccode.config.paths import EaccodePaths
from eaccode.config.providers import ProviderConfig, load_providers, save_providers
from eaccode.config.settings import Settings


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0", prog_name="eaccode")
@click.pass_context
def main(ctx: click.Context) -> None:
    """eaccode — autonomer Coding-Agent (BYOK)."""
    if ctx.invoked_subcommand is None:
        click.echo("eaccode — REPL kommt in Phase 7. Verfügbare Befehle: eaccode --help")


@main.command()
def paths() -> None:
    """Zeige aufgelöste Konfigurations-/Datenpfade."""
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
    """BYOK-Provider verwalten."""


@providers.command("add")
@click.option("--provider", required=True, help="Provider-Name (minimax, anthropic, opencode-go, ...)")
@click.option("--model", required=True, help="Standard-Modell dieses Providers")
@click.option("--api-key", prompt=True, hide_input=True, help="API-Key (wird versteckt abgefragt)")
@click.option("--base-url", default=None, help="Custom API-Base-URL (OpenAI-kompatible Endpoints)")
def providers_add(provider: str, model: str, api_key: str, base_url: str | None) -> None:
    """Provider + API-Key hinzufügen (BYOK)."""
    paths = EaccodePaths()
    existing = load_providers(paths.providers_file)
    for p in existing:
        if p.name == provider:
            click.echo(f"✗ Provider '{provider}' existiert bereits — erst entfernen oder direkt in {paths.providers_file} bearbeiten.")
            raise SystemExit(1)
    existing.append(
        ProviderConfig(name=provider, api_key=api_key, model=model, base_url=base_url)  # type: ignore[arg-type]
    )
    save_providers(existing, paths.providers_file)
    paths.providers_file.chmod(0o600)
    click.echo(f"✓ {provider} → {model} gespeichert ({paths.providers_file})")


@providers.command("list")
def providers_list() -> None:
    """Konfigurierte Provider anzeigen (Keys maskiert)."""
    paths = EaccodePaths()
    providers_list = load_providers(paths.providers_file)
    if not providers_list:
        click.echo("Keine Provider konfiguriert. Hinzufügen mit: eaccode providers add")
        return
    for p in providers_list:
        key = p.api_key.get_secret_value()
        masked = f"{key[:4]}…{key[-2:]}" if len(key) > 6 else "***"
        suffix = f" (base_url: {p.base_url})" if p.base_url else ""
        click.echo(f"  {p.name:14s} {p.model:30s} key={masked}{suffix}")


@providers.command("remove")
@click.argument("name")
def providers_remove(name: str) -> None:
    """Provider entfernen."""
    paths = EaccodePaths()
    existing = load_providers(paths.providers_file)
    remaining = [p for p in existing if p.name != name]
    if len(remaining) == len(existing):
        click.echo(f"✗ Provider '{name}' nicht gefunden.")
        raise SystemExit(1)
    save_providers(remaining, paths.providers_file)
    click.echo(f"✓ {name} entfernt")


@providers.command("set-default")
@click.argument("name")
def providers_set_default(name: str) -> None:
    """Standard-Provider für neue Sessions setzen."""
    paths = EaccodePaths()
    if not any(p.name == name for p in load_providers(paths.providers_file)):
        click.echo(f"✗ Provider '{name}' nicht konfiguriert.")
        raise SystemExit(1)
    settings = Settings.load(paths.settings_file)
    settings.default_provider = name
    settings.save(paths.settings_file)
    click.echo(f"✓ Standard-Provider: {name}")


# ------------------------------------------------------------------ config

@main.group()
def config() -> None:
    """Settings anzeigen und ändern."""


@config.command("show")
def config_show() -> None:
    """Aktuelle Settings anzeigen."""
    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    for k, v in settings.model_dump(mode="json").items():
        click.echo(f"  {k:24s} {v}")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Setting setzen, z.B. `eaccode config set permission_mode acceptEdits`."""
    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    if key not in Settings.model_fields:
        click.echo(f"✗ Unbekanntes Setting: {key}. Bekannt: {', '.join(Settings.model_fields)}")
        raise SystemExit(1)
    # Pydantic validiert selbst (Enum, int, bool, float, Constraints wie ge=1)
    try:
        updated = Settings.model_validate({**settings.model_dump(), key: value})
    except Exception as e:
        click.echo(f"✗ Ungültiger Wert für {key}: {value} ({e})")
        raise SystemExit(1)
    updated.save(paths.settings_file)
    value_out = getattr(updated, key)
    click.echo(f"✓ {key} = {value_out.value if hasattr(value_out, 'value') else value_out}")


if __name__ == "__main__":
    main()
