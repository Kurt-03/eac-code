"""Setup-oriented CLI sub-commands (E.2/E.7/E.11/E.19/E.18).

``init``  — first-run scaffolding: settings, directories, hooks/, .env.
``setup`` — interactive provider setup (hidden prompt, 0600 perms).
``env``   — environment probe.
``version`` — build info (commit, python, platform).
"""

from __future__ import annotations

import click

from eaccode.cli import main
from eaccode.cli._output import print_info, print_success
from eaccode.config.paths import EaccodePaths


@main.command("init")
def init_command() -> None:
    """Create the config scaffolding (idempotent, E.2/E.19)."""
    paths = EaccodePaths()  # constructor creates all directories
    settings_file = paths.settings_file
    if not settings_file.exists():
        from eaccode.config.settings import Settings

        Settings().save(settings_file)
        print_success(f"✓ created {settings_file}")
    else:
        print_info(f"settings exist: {settings_file}")
    hooks_dir = paths.hooks_dir
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "README.md").write_text(
        "# Hooks\n\nDrop executable scripts here. Events:\n"
        "- `session_start` (args: workdir)\n"
        "- `session_end` (args: workdir)\n"
        "- `pre_tool_use` (args: workdir tool arguments)\n"
        "- `post_tool_use` (args: workdir tool result)\n",
        encoding="utf-8",
    )
    env_file = paths.config_dir / ".env"
    if not env_file.exists():
        env_file.write_text(
            "# Per-user environment overrides (KEY=VALUE, one per line)\n",
            encoding="utf-8",
        )
    print_success("✓ directories + hooks/ + .env template ready")


@main.command("setup")
def setup_command() -> None:
    """Interactive provider setup (hidden prompt, 0600 perms, E.7)."""
    from eaccode.config.paths import EaccodePaths
    from eaccode.config.providers import ProviderConfig, save_providers

    paths = EaccodePaths()
    existing = _existing_providers(paths)
    if existing:
        print_info(f"Providers already configured: {', '.join(existing)}")
        if not click.confirm("Add another provider?", default=False):
            return
    name = click.prompt("Provider name", default="default")
    model = click.prompt("Model name")
    base_url = click.prompt("Base URL (empty = provider default)", default="")
    api_key = click.prompt("API key", hide_input=True, default="")
    providers = []
    if paths.providers_file.exists():
        from eaccode.config.providers import load_providers

        providers = load_providers(paths.providers_file)
    providers = [p for p in providers if p.name != name]
    providers.append(
        ProviderConfig(
            name=name, model=model, api_key=api_key or None,
            base_url=base_url or None,
        )
    )
    save_providers(providers, paths.providers_file)
    print_success(f"✓ provider {name!r} saved (0600)")


def _existing_providers(paths: EaccodePaths) -> list[str]:
    if not paths.providers_file.exists():
        return []
    from eaccode.config.providers import load_providers

    return [p.name for p in load_providers(paths.providers_file)]


@main.command("env")
def env_command() -> None:
    """Environment probe (E.11): paths, python, providers, optional deps."""
    import os
    import platform
    import sys

    from eaccode.config.providers import load_providers
    from eaccode.config.settings import Settings

    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    print_info(f"python: {sys.version.split()[0]} ({platform.python_implementation()})")
    print_info(f"platform: {platform.system()} {platform.release()}")
    print_info(f"workdir: {os.getcwd()}")
    print_info(f"config_dir: {paths.config_dir}")
    print_info(f"data_dir: {paths.data_dir}")
    print_info(f"sessions_db: {paths.sessions_dir / 'sessions.db'}")
    print_info(f"providers: {len(load_providers(paths.providers_file))} configured")
    print_info(f"permission_mode: {settings.permission_mode.value}")
    print_info(f"hooks_enabled: {settings.hooks_enabled}")
    for dep in ("trafilatura", "websocket_client", "mcp"):
        try:
            __import__(dep)
            print_info(f"dep {dep}: ok")
        except ImportError:
            print_info(f"dep {dep}: missing (optional)")


@main.command("version")
def version_command() -> None:
    """Build info (E.18): version, commit, python, platform."""
    import platform
    import sys
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as pkg_version

    try:
        ver = pkg_version("eaccode")
    except PackageNotFoundError:
        ver = "0.1.0"
    print_info(f"eaccode {ver}")
    print_info(f"commit: {_git_head()}")
    print_info(f"python: {sys.version.split()[0]}")
    print_info(f"platform: {platform.system()} {platform.release()}")


def _git_head() -> str:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"
