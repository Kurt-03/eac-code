"""Checkpoints (Phase C.4) — file snapshots before write/edit, /rollback.

Copies the affected file into the project-hashed directory under the
config data path before the first modification of a turn; /rollback
lists and restores them. ``workdir`` is hashed with ``MemoryStore.project_hash``
so each project has its own checkpoint bucket and we don't litter
``<workdir>/.eaccode/checkpoints/`` in every visited folder.

P0.1 (audit): storage moved out of the working directory. Before, every
``cd`` into a project left a ``.eaccode/`` folder behind; on Windows the
folder sometimes landed in ``C:\\WINDOWS\\System32\\`` where the
checkpoint write itself was the failure that killed the user's write.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def checkpoint_dir(workdir: Path) -> Path:
    """Project-hashed checkpoint bucket under the eaccode data path.

    Layout: ``<data_dir>/checkpoints/<project_hash>/``.

    Special case: when ``workdir`` lives inside pytest's tempdir (the
    common test setup), the bucket is colocated with the workdir instead
    — otherwise every test in the repo shares the same git-root hash and
    the bucket fills up across the test session.
    """
    import tempfile

    tmp_root = Path(tempfile.gettempdir()).resolve()
    try:
        in_tmp = str(workdir.resolve()).startswith(str(tmp_root))
    except OSError:
        in_tmp = False
    if in_tmp:
        return workdir / ".eaccode" / "checkpoints"

    from eaccode.config.paths import EaccodePaths
    from eaccode.memory.store import MemoryStore

    base = EaccodePaths().data_dir / "checkpoints"
    project_hash = MemoryStore.project_hash(workdir)
    return base / project_hash


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


def cleanup_old_checkpoints(workdir: Path, max_age_days: int = 7) -> int:
    """F.26: remove checkpoint files older than *max_age_days*; returns count."""
    import time

    cdir = checkpoint_dir(workdir)
    if not cdir.is_dir():
        return 0
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    for f in cdir.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            pass
    return removed


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
