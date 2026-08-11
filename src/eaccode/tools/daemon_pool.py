"""Daemon pool (G.3) — bounded slots for long-running helper processes.

The agent can park dev servers/watchers here (max ``slots``). The pool
shares the process registry (G.2) so session exit kills everything.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from eaccode.tools.process_registry import kill, register


@dataclass
class DaemonSlot:
    key: str
    pid: int
    command: str


class DaemonPool:
    def __init__(self, slots: int = 2) -> None:
        self.slots = max(1, slots)
        self._lock = Lock()
        self._daemons: dict[str, DaemonSlot] = {}

    def add(self, key: str, pid: int, command: str) -> str | None:
        """Park a daemon; returns an error message when the pool is full."""
        with self._lock:
            if key in self._daemons:
                return f"daemon {key!r} is already parked"
            if len(self._daemons) >= self.slots:
                return (f"daemon pool full ({self.slots} slots) — "
                        "stop one first")
            register(pid, command)
            self._daemons[key] = DaemonSlot(key, pid, command)
            return None

    def stop(self, key: str) -> bool:
        with self._lock:
            slot = self._daemons.pop(key, None)
        return bool(slot and kill(slot.pid))

    def stop_all(self) -> int:
        stopped = 0
        for key in list(self._daemons):
            if self.stop(key):
                stopped += 1
        return stopped

    def list(self) -> list[DaemonSlot]:
        with self._lock:
            return list(self._daemons.values())

    def is_full(self) -> bool:
        with self._lock:
            return len(self._daemons) >= self.slots
