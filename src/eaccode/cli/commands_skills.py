"""`eaccode skills bundle` sub-commands (A.11) — bundle install + listing.

Extends the existing ``skills`` group (defined in commands_utility) with
a ``bundle`` sub-command; ``skills list`` stays in commands_utility.
"""

from pathlib import Path

import click

from eaccode.cli._output import print_info, print_warn
from eaccode.cli.commands_utility import skills
from eaccode.config.paths import EaccodePaths
from eaccode.memory.skill_bundles import install_bundle, scan_bundles


@skills.command("bundle")
@click.argument("action", type=click.Choice(["list", "install"]))
@click.argument("name", required=False)
def skills_bundle(action: str, name: str | None) -> None:
    """List or install local skill bundles."""
    paths = EaccodePaths()
    package_bundles = Path(__file__).resolve().parent.parent / "bundles"
    bundles_dirs = [
        paths.config_dir / "bundles",  # user-managed
        package_bundles,               # shipped with the package
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
