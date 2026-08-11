"""CLI sub-commands — registered onto the main click group on import."""
from __future__ import annotations

from pathlib import Path

import click

from eaccode.cli import main
from eaccode.cli._output import print_error, print_info, print_success
from eaccode.cli.commands_config import config
from eaccode.config.paths import EaccodePaths
from eaccode.config.providers import load_providers
from eaccode.config.settings import Settings

# ------------------------------------------------------------------- doctor

@main.command("doctor")
def doctor() -> None:
    """Diagnose the installation: providers, settings, git, skills, MCP."""
    paths = EaccodePaths()
    problems = 0

    def check(ok: bool, msg: str) -> None:
        nonlocal problems
        print_info(f"  {'✓' if ok else '✗'} {msg}")
        if not ok:
            problems += 1

    print_info("eaccode doctor")
    providers = load_providers(paths.providers_file)
    check(bool(providers), f"providers configured ({len(providers)})")
    for p in providers:
        print_info(f"      {p.name:14s} {p.model}")
    settings = Settings.load(paths.settings_file)
    check(settings.permission_mode.value in ("default", "acceptEdits", "plan", "bypassPermissions"),
          f"settings loadable (mode={settings.permission_mode.value})")
    check(paths.skills_dir.exists(), f"skills dir exists ({paths.skills_dir})")
    try:
        subprocess_run = __import__("subprocess").run(
            ["git", "--version"], capture_output=True, timeout=10
        )
        check(subprocess_run.returncode == 0, "git available")
    except Exception:
        check(False, "git available")
    from eaccode.tools.mcp.client import load_mcp_configs

    mcp_configs = load_mcp_configs(paths.config_dir / "mcp.yaml")
    check(len(mcp_configs) >= 0, f"mcp.yaml ({len(mcp_configs)} server(s) configured)")

    # E.15: extended diagnostics.
    for dep, purpose in (("trafilatura", "web_extract"),
                         ("websocket-client", "browser CDP")):
        try:
            __import__(dep)
            check(True, f"{purpose} dep available ({dep})")
        except ImportError:
            check(False, f"{purpose} dep missing ({dep} — optional, "
                         "`eaccode deps` installs)")
    allowlist = paths.config_dir / "allowlist.json"
    check(not allowlist.exists() or allowlist.stat().st_size > 2,
          f"allowlist loadable ({allowlist.name})")
    try:
        import sqlite3

        with sqlite3.connect(paths.sessions_dir / "sessions.db"):
            check(True, "sessions DB openable")
    except Exception:
        check(False, "sessions DB openable")
    hooks = paths.hooks_dir
    from eaccode.hooks.registry import discover_hooks

    hook_count = sum(len(v) for v in discover_hooks(hooks).values())
    check(hook_count >= 0, f"hooks dir ({hook_count} script(s))")
    for p in providers:
        has_key = bool(p.api_key)
        has_env = bool(getattr(p, "api_key_env", None))
        check(has_key or has_env,
              f"provider {p.name}: key set "
              f"({'env' if has_env else 'file' if has_key else 'MISSING'})")

    if problems:
        print_info(f"\n{problems} issue(s) found.")
        raise SystemExit(1)
    print_info("\nAll checks passed.")


# ------------------------------------------------------------------ models

@main.group()
def models_cmd() -> None:
    """Show configured models and their capabilities."""


@models_cmd.command("list")
def models_list() -> None:
    """List configured providers/models with thinking capabilities."""
    from eaccode.llm.thinking import ThinkingMapper

    paths = EaccodePaths()
    mapper = ThinkingMapper()
    providers_list = load_providers(paths.providers_file)
    if not providers_list:
        print_info("No providers configured.")
        return
    for p in providers_list:
        litellm_id = p.litellm_model(p.model)
        thinking = mapper.supports_thinking(litellm_id)
        print_info(
            f"  {p.name:14s} {p.model:30s} thinking={'✓' if thinking else '✗'}  "
            f"({litellm_id})"
        )


# ------------------------------------------------------------------ skills

@main.group()
def skills() -> None:
    """Manage skills (markdown instructions the agent loads)."""


@skills.command("list")
def skills_list() -> None:
    """List installed skills."""
    from eaccode.memory.skills import discover_skills

    paths = EaccodePaths()
    installed = discover_skills([paths.skills_dir])
    if not installed:
        print_info(f"No skills installed. Put .md files in {paths.skills_dir}")
        return
    for s in installed:
        print_info(f"  {s.name:25s} {s.description}")


@skills.command("add")
@click.argument("path")
def skills_add(path: str) -> None:
    """Import a skill markdown file into the skills directory."""
    import shutil

    from eaccode.memory.skills import _parse_frontmatter

    paths = EaccodePaths()
    src = Path(path)
    if not src.exists():
        print_error(f"✗ File not found: {src}")
        raise SystemExit(1)
    meta, _ = _parse_frontmatter(src.read_text(encoding="utf-8"))
    name = meta.get("name") or src.stem
    paths.skills_dir.mkdir(parents=True, exist_ok=True)
    dest = paths.skills_dir / f"{name}.md"
    shutil.copy2(src, dest)
    print_success(f"✓ Skill '{name}' installed at {dest}")


# --------------------------------------------------------------- config init

@config.command("init")
def config_init() -> None:
    """Create .eaccode/ with an EACCODE.md template in the current project."""
    project_dir = Path.cwd()
    dot_dir = project_dir / ".eaccode"
    dot_dir.mkdir(exist_ok=True)
    ctx_file = project_dir / "EACCODE.md"
    if not ctx_file.exists():
        ctx_file.write_text(
            "# EACCODE.md — project rules for eaccode\n\n"
            "## Build\n- (add your build/test commands here)\n\n"
            "## Conventions\n- (add style/code conventions here)\n",
            encoding="utf-8",
        )
    print_success(f"✓ Created {ctx_file}")
    print_success(f"✓ Created {dot_dir} (put project skills here)")


