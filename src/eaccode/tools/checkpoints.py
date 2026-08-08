"""Checkpoints (Phase C.4) — file snapshots before write/edit, /rollback.

Copies the affected file into .eaccode/checkpoints/ before the first
modification of a turn; /rollback lists and restores them.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def checkpoint_dir(workdir: Path) -> Path:
    return workdir / ".eaccode" / "checkpoints"


def save_checkpoint(workdir: Path, target: Path) -> Path | None:
    """Snapshot *target* if it exists; returns the checkpoint path or None.

    A small JSON sidecar stores the original filename (timestamps and
    filenames both contain underscores, so the name is not recoverable
    from the checkpoint filename alone).
    """
    import json

    if not target.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    cdir = checkpoint_dir(workdir)
    cdir.mkdir(parents=True, exist_ok=True)
    name = target.name.replace(".", "_")
    dest = cdir / f"{ts}_{name}.bak"
    dest.write_bytes(target.read_bytes())
    sidecar = cdir / f"{ts}_{name}.json"
    sidecar.write_text(json.dumps({"original": target.name}), encoding="utf-8")
    return dest


def list_checkpoints(workdir: Path) -> list[Path]:
    cdir = checkpoint_dir(workdir)
    if not cdir.exists():
        return []
    return sorted(cdir.glob("*.bak"), reverse=True)


def restore_checkpoint(workdir: Path, checkpoint: Path) -> bool:
    """Restore a checkpoint into the workdir (name from its sidecar)."""
    import json

    if not checkpoint.exists():
        return False
    sidecar = checkpoint.with_suffix(".json")
    if not sidecar.exists():
        return False
    try:
        original_name = json.loads(sidecar.read_text(encoding="utf-8"))["original"]
    except Exception:
        return False
    dest = workdir / original_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(checkpoint.read_bytes())
    return True
