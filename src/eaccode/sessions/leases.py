"""Active-session leases (D.8) — cross-process lock files.

Each running session holds ``sessions/<id>.lock`` with its pid + start
time. Stale locks (pid no longer alive) are cleared on startup so a
crashed session cannot block the listing forever.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def acquire_lease(sessions_dir: Path, session_id: str) -> Path:
    """Create the lock file; returns it."""
    sessions_dir.mkdir(parents=True, exist_ok=True)
    lock = sessions_dir / f"{session_id}.lock"
    lock.write_text(
        json.dumps({"pid": os.getpid(), "session": session_id}),
        encoding="utf-8",
    )
    return lock


def release_lease(lock: Path) -> None:
    from contextlib import suppress

    with suppress(OSError):
        lock.unlink()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)  # signal 0 only probes existence
        return True
    except OSError:
        return False


def cleanup_stale_leases(sessions_dir: Path) -> int:
    """Remove locks whose pid is gone; returns the number removed."""
    if not sessions_dir.is_dir():
        return 0
    removed = 0
    for lock in sessions_dir.glob("*.lock"):
        try:
            data = json.loads(lock.read_text(encoding="utf-8"))
            pid = int(data.get("pid", -1))
        except (OSError, ValueError):
            pid = -1
        if not _pid_alive(pid):
            try:
                lock.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def active_leases(sessions_dir: Path) -> list[str]:
    """Session ids of all (live) leases."""
    if not sessions_dir.is_dir():
        return []
    active: list[str] = []
    for lock in sessions_dir.glob("*.lock"):
        try:
            data = json.loads(lock.read_text(encoding="utf-8"))
            if _pid_alive(int(data.get("pid", -1))):
                active.append(str(data.get("session", lock.stem)))
        except (OSError, ValueError):
            pass
    return active
