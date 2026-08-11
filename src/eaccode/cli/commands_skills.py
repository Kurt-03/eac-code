"""`eaccode skills` sub-commands (A.11) — bundle install + listing."""

import click

from eaccode.cli._output import print_info, print_warn
from eaccode.config.paths import EaccodePaths
from eaccode.memory.skill_bundles import install_bundle, scan_bundles
from eaccode.memory.skill_linter import lint_skills_dir


@click.group(name="skills")
def skills_group() -> None:
    """Manage skills and skill bundles."""


@skills_group.command("list")
def skills_list() -> None:
    """List installed skills (with lint status)."""
    paths = EaccodePaths()
    from eaccode.memory.skills import discover_skills

    skills = discover_skills([paths.skills_dir])
    if not skills:
        print_info("No skills installed yet.")
        return
    lint = lint_skills_dir(paths.skills_dir)
    for s in skills:
        status = "✓" if str(s.source) not in lint else f"✗ ({len(lint[str(s.source)])} lint)"
        print_info(f"- {s.name}: {s.description} [{s.provenance}] {status}")


@skills_group.command("bundle")
@click.argument("action", type=click.Choice(["list", "install"]))
@click.argument("name", required=False)
def skills_bundle(action: str, name: str | None) -> None:
    """List or install local skill bundles."""
    paths = EaccodePaths()
    bundles_dirs = [
        paths.config_dir / "bundles",
        # Bundles shipped with the package (if the repo layout is present).
        paths.config_dir.parent / "src" / "eaccode" / "bundles",
    ]
    if action == "list":
        bundles = scan_bundles(bundles_dirs)
        if not bundles:
            print_info("No bundles found.")
            return
        for bname, bdir in sorted(bundles.items()):
            print_info(f"- {bname} ({bdir})")
        return
    if not name:
        print_warn("Usage: eaccode skills bundle install <name>")
        raise SystemExit(2)
    installed = install_bundle(name, bundles_dirs, paths.skills_dir)
    if installed is None:
        print_warn(f"Bundle '{name}' not found. 'eaccode skills bundle list' shows all.")
        raise SystemExit(1)
    print_info(f"Installed bundle '{name}' → {installed}")
