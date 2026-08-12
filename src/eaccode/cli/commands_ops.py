"""Operations CLI sub-commands (E.8/E.12/E.13/E.14/E.16/E.17).

``backup`` — snapshot memory + skills + settings (curator/backup.py).
``update`` — check the git remote for newer commits (no auto-pull).
``deps``   — optional dependency report + install hint.
``dump``   — redacted config/system-prompt dump for debugging.
``hooks``  — list hook scripts in the hooks dir.
``plugins`` — list installed context-engine plugins.
"""

from __future__ import annotations

import click

from eaccode.cli import main
from eaccode.cli._output import print_error, print_info, print_success
from eaccode.config.paths import EaccodePaths


@main.group()
def backup() -> None:
    """Backup memory, skills and settings (E.13)."""


@backup.command("create")
def backup_create() -> None:
    """Create a snapshot zip."""
    from eaccode.config.settings import Settings
    from eaccode.curator.backup import backup_snapshot

    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    dest = backup_snapshot(
        paths.skills_dir, paths.memory_dir, paths.data_dir / "backups"
    )
    # E.3: prune old backups beyond backup_keep_days.
    if settings.backup_keep_days > 0:
        import time

        cutoff = time.time() - settings.backup_keep_days * 86400
        for old in sorted(paths.data_dir.glob("backups/eaccode-backup-*.zip"),
                          key=lambda p: p.stat().st_mtime):
            if old.stat().st_mtime < cutoff:
                try:
                    old.unlink()
                    print_info(f"pruned {old.name}")
                except OSError:
                    pass
    print_success(f"✓ backup → {dest}")


@backup.command("list")
def backup_list() -> None:
    """List backups (newest first)."""
    from eaccode.curator.backup import list_backups

    paths = EaccodePaths()
    backups = list_backups(paths.data_dir / "backups")
    if not backups:
        print_info("no backups yet")
        return
    for b in backups:
        print_info(f"  {b.name}  ({b.stat().st_size} bytes)")


@main.command("update")
def update_command() -> None:
    """Check the git remote for newer commits (E.14, no auto-pull)."""
    import subprocess

    from eaccode._subprocess_compat import bounded_git_probe, windows_hide_flags

    # D3 (audit): git runs need the repo cwd, hidden windows and
    # returncode checks — previously 'update' outside a repo printed
    # raw 'fatal: not a git repository' and then a false claim.
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=10,
        creationflags=windows_hide_flags(),
        check=False,
    )
    if root.returncode != 0:
        print_info("not a git repository — update check skipped")
        return
    repo_dir = root.stdout.strip()
    try:
        fetch = subprocess.run(
            ["git", "fetch", "--quiet"], timeout=30, check=False,
            cwd=repo_dir, creationflags=windows_hide_flags(),
        )
        if fetch.returncode != 0:
            print_error("git fetch failed — is the remote reachable?")
            return
        head = bounded_git_probe(
            ["git", "rev-parse", "HEAD"], timeout=10,
        ).strip()
        remote = bounded_git_probe(
            ["git", "rev-parse", "@{u}"], timeout=10,
        ).strip()
        if not head or not remote:
            print_info("no upstream configured — update check skipped")
            return
        count = bounded_git_probe(
            ["git", "rev-list", "--count", f"{head}..{remote}"],
            timeout=10,
        ).strip()
        if count == "0":
            print_success("✓ up to date")
        else:
            print_info(f"{count} new commit(s) on the remote — run "
                       "`git pull --ff-only` to update")
    except Exception as e:
        print_error(f"update check failed: {e}")


@main.command("deps")
def deps_command() -> None:
    """Optional dependency report (E.17)."""
    optional = {
        "trafilatura": "web_extract (web page to text)",
        "websocket-client": "browser automation (CDP)",
        "mcp": "MCP servers",
    }
    missing = []
    for dep, purpose in optional.items():
        try:
            __import__(dep)
            print_info(f"  {dep}: ok ({purpose})")
        except ImportError:
            missing.append(dep)
            print_info(f"  {dep}: missing ({purpose})")
    if missing:
        print_info("Install optional deps: "
                   "uv pip install " + " ".join(missing))
    else:
        print_success("✓ all optional deps present")


@main.command("dump")
@click.option("--workdir", default=None, help="Project dir (default: cwd)")
def dump_command(workdir: str | None) -> None:
    """Redacted system-prompt/config dump for debugging (E.16)."""
    import asyncio
    from pathlib import Path

    from eaccode.agent.factory import build_system_context_async
    from eaccode.config.providers import load_providers
    from eaccode.config.settings import Settings
    from eaccode.security.redact import redact_secrets

    paths = EaccodePaths()
    wd = Path(workdir or ".").resolve()
    settings = Settings.load(paths.settings_file)
    providers = load_providers(paths.providers_file)
    print_info(f"# settings ({paths.settings_file})")
    print_info(redact_secrets(settings.model_dump_json(indent=2)))
    print_info(f"# providers: {len(providers)} configured "
               f"(names only: {[p.name for p in providers]})")
    ctx = asyncio.run(
        build_system_context_async(wd, skills_dirs=[paths.skills_dir],
                                   ignore_rules=settings.ignore_rules)
    )
    print_info("# system prompt")
    print_info(redact_secrets(ctx.system_prompt))
    print_info(f"# memory facts: {len(ctx.memory_facts)}")


@main.command("recipes")
def recipes_command() -> None:
    """List reusable prompt recipes (J.15/J.27)."""
    from eaccode.config.paths import EaccodePaths

    recipes_dir = EaccodePaths().recipes_dir
    recipes = sorted(recipes_dir.glob("*.md"))
    if not recipes:
        print_info(f"No recipes yet — drop markdown files into {recipes_dir}")
        return
    for r in recipes:
        head = r.read_text(encoding="utf-8", errors="replace").splitlines()
        title = next((ln for ln in head if ln.startswith("# ")), r.stem)
        print_info(f"  {r.stem:24s} {title.lstrip('# ')[:60]}")


@main.command("manifest")
def manifest_command() -> None:
    """Show project manifest info (J.18)."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as pkg_version

    from eaccode.cli import main as _main

    print_info(f"commands: {len(_main.commands)}")
    try:
        print_info(f"version: {pkg_version('eaccode')}")
    except PackageNotFoundError:
        print_info("version: 0.0.1 (editable install)")
    import sys

    print_info(f"python: {sys.version.split()[0]}")
    from eaccode.config.paths import EaccodePaths

    p = EaccodePaths()
    print_info(f"config: {p.config_dir}")
    print_info(f"data: {p.data_dir}")
    print_info(f"cron db: {p.cron_db}")


@main.command("hooks")
def hooks_command() -> None:
    """List hook scripts (E.12)."""
    from eaccode.hooks.registry import discover_hooks

    paths = EaccodePaths()
    hooks = discover_hooks(paths.hooks_dir)
    if not hooks:
        print_info("no hooks installed (drop scripts into "
                   f"{paths.hooks_dir})")
        return
    for event in sorted(hooks):
        print_info(f"  {event}: {', '.join(str(h) for h in hooks[event])}")


@main.command("plugins")
def plugins_command() -> None:
    """List installed context-engine plugins (E.8)."""
    from eaccode.config.paths import EaccodePaths

    paths = EaccodePaths()
    plugin_dir = paths.plugins_dir
    if not plugin_dir.is_dir():
        print_info(f"no plugins (create {plugin_dir})")
        return
    found = [p for p in sorted(plugin_dir.iterdir()) if p.is_dir()]
    if not found:
        print_info(f"no plugins in {plugin_dir}")
        return
    for p in found:
        entry = p / "plugin.yaml"
        meta = ""
        if entry.exists():
            try:
                import yaml

                meta = str(yaml.safe_load(entry.read_text(encoding="utf-8"))
                           .get("name", ""))
            except Exception:
                meta = "(invalid plugin.yaml)"
        print_info(f"  {p.name}: {meta}")
