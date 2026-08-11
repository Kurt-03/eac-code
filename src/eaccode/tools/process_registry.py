"""Process registry (G.2) — track spawned processes across the session.

The process tool registers every spawn here so the REPL status line and
``process list`` can show what is running, and the exit path can kill
stragglers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ProcessEntry:
    pid: int
    command: str
    started_at: float = field(default_factory=time.time)
    status: str = "running"  # running | done | killed


_registry: dict[int, ProcessEntry] = {}
_lock = Lock()


def register(pid: int, command: str) -> None:
    with _lock:
        _registry[pid] = ProcessEntry(pid=pid, command=command[:200])


def mark_done(pid: int) -> None:
    with _lock:
        entry = _registry.get(pid)
        if entry is not None:
            entry.status = "done"


def kill(pid: int) -> bool:
    """Kill a registered process; True when it was running."""
    with _lock:
        entry = _registry.get(pid)
        if entry is None or entry.status != "running":
            return False
        import os

        try:
            os.kill(pid, 9)
        except OSError:
            return False
        entry.status = "killed"
        return True


def list_processes() -> list[ProcessEntry]:
    with _lock:
        return sorted(_registry.values(), key=lambda e: e.started_at)


def kill_all() -> int:
    """Kill every still-running process (session exit); returns count."""
    killed = 0
    for entry in list_processes():
        if entry.status == "running" and kill(entry.pid):
            killed += 1
    return killed
