"""Local skill bundles (A.11) — install pre-made skills from a bundles dir.

A bundle is a directory containing ``SKILL.md`` (plus optional
scripts/templates). Bundles live in the eaccode package
(``src/eaccode/bundles/<name>/``) or in the user's config dir
(``config_dir/bundles/<name>/``). ``install_bundle`` copies the bundle
into the skills directory — provenance becomes ``bundled`` because of
the directory layout (see skills.py).
"""

from __future__ import annotations

import shutil
from pathlib import Path

BUNDLE_FILE = "SKILL.md"


def scan_bundles(bundles_dirs: list[Path]) -> dict[str, Path]:
    """name -> bundle directory, for every dir containing SKILL.md."""
    result: dict[str, Path] = {}
    for base in bundles_dirs:
        if not base.is_dir():
            continue
        for bundle_dir in sorted(base.iterdir()):
            if bundle_dir.is_dir() and (bundle_dir / BUNDLE_FILE).exists():
                result[bundle_dir.name] = bundle_dir
    return result


def install_bundle(name: str, bundles_dirs: list[Path],
                   target_dir: Path) -> Path | None:
    """Copy *name* into *target_dir*/bundled/<name>/; None when missing.

    Installing under a ``bundled/`` subdir makes provenance detection
    (skills.py) mark it as bundled automatically.
    """
    bundles = scan_bundles(bundles_dirs)
    src = bundles.get(name)
    if src is None:
        return None
    dest = target_dir / "bundled" / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest / BUNDLE_FILE


def bundle_skill_files(bundle_dir: Path) -> list[Path]:
    """Markdown files inside a bundle (SKILL.md first)."""
    files = sorted(bundle_dir.rglob("*.md"))
    files.sort(key=lambda p: (p.name != BUNDLE_FILE, str(p)))
    return files
