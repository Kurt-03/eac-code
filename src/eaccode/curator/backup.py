"""Curator backup (C.6) — snapshot skills + memory before curator changes.

A timestamped zip of the skills and memory directories; backups live in
``data_dir/backups/``. Restoring is manual (unzip) — the backup exists
so an automated curation pass can always be undone.
"""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

BACKUP_PREFIX = "eaccode-backup"


def backup_snapshot(skills_dir: Path, memory_dir: Path,
                    backup_dir: Path) -> Path:
    """Zip skills + memory into *backup_dir*; returns the zip path."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"{BACKUP_PREFIX}-{stamp}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for base, label in ((skills_dir, "skills"), (memory_dir, "memory")):
            if not base.is_dir():
                continue
            for f in base.rglob("*"):
                if f.is_file():
                    zf.write(f, arcname=f"{label}/{f.relative_to(base)}")
    return dest


def list_backups(backup_dir: Path) -> list[Path]:
    """Backup zips, newest first."""
    if not backup_dir.is_dir():
        return []
    return sorted(
        backup_dir.glob(f"{BACKUP_PREFIX}-*.zip"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )


def restore_backup(zip_path: Path, target_dir: Path) -> None:
    """Extract a backup zip into *target_dir* (creates skills/ + memory/)."""
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if not member.startswith(("skills/", "memory/")):
                continue
            relative = member.split("/", 1)[1]
            if not relative:
                continue
            dest = target_dir / relative
            if member.endswith("/"):
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(member))
