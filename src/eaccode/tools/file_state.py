"""File-state coordination (P0.5) — per-path locks + stale-write detection.

Two agents (or the main agent and a subagent) editing the same file is a
silent corruption source. This module gives each write a chance to check
whether another writer touched the path since it last read it:

- ``lock_path(path)`` — re-entrant per-path lock (thread scope; eaccode
  subagents share the process).
- ``touch(path, writer_id)`` — record a write.
- ``read_stamp(path)`` / ``check_stale(writer_id, path, since_ts)`` —
  stale detection: did anyone write *after* my read?
- ``writes_since(since_ts, paths)`` — conflict report for subagent
  results (which of my paths changed while the subagent worked).

Everything is in-memory (thread-scope, per Hermes' design minus the
cross-process layers) — process-local coordination only.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

_lock = threading.RLock()
_stamps: dict[str, float] = {}  # resolved path -> last write ts
_locks: dict[str, threading.RLock] = {}
_writers: dict[str, str] = {}  # resolved path -> last writer id


def _key(path: Path | str) -> str:
    return str(Path(path).resolve())


def lock_path(path: Path | str):
    """Re-entrant per-path lock (context manager).

    Guards read-modify-write sequences on the same path within the
    process — the main agent and subagents share this registry.
    """
    key = _key(path)
    with _lock:
        per_path = _locks.get(key)
        if per_path is None:
            per_path = _locks[key] = threading.RLock()
    return per_path


def touch(path: Path | str, writer_id: str = "main") -> None:
    """Record that *writer_id* wrote to *path* (call while holding the lock)."""
    key = _key(path)
    with _lock:
        _stamps[key] = time.monotonic()
        _writers[key] = writer_id


def last_write_ts(path: Path | str) -> float | None:
    key = _key(path)
    with _lock:
        return _stamps.get(key)


def last_writer(path: Path | str) -> str | None:
    key = _key(path)
    with _lock:
        return _writers.get(key)


def check_stale(writer_id: str, path: Path | str, since_ts: float) -> bool:
    """True when another writer touched *path* after *since_ts*.

    A writer that only reads *path* at ``since_ts`` and writes later must
    call this before writing: True means "someone else wrote in between —
    your write would clobber theirs".
    """
    key = _key(path)
    with _lock:
        stamp = _stamps.get(key)
        if stamp is None:
            return False
        writer = _writers.get(key)
        return stamp > since_ts and writer != writer_id


def writes_since(since_ts: float, paths: list[Path | str]) -> list[str]:
    """Paths from *paths* that were written by anyone after *since_ts*.

    For subagent conflict detection: run before delegating (ts), then
    compare the subagent's touched paths against this after it returns.
    """
    with _lock:
        return [
            str(p) for p in paths
            if _stamps.get(_key(p), 0.0) > since_ts
        ]


def writes_by(since_ts: float, writer_ids: set[str]) -> list[tuple[str, str]]:
    """(path, writer) pairs written after *since_ts* by the given writers.

    Subagent attribution: the delegate records a timestamp before the
    subagent runs and reports the paths this subagent wrote afterwards.
    """
    with _lock:
        return [
            (k, _writers.get(k, "")) for k, v in _stamps.items()
            if v > since_ts and _writers.get(k) in writer_ids
        ]


def snapshot_writes() -> dict[str, tuple[str, float]]:
    """Full write ledger (path -> writer, ts) for debugging/tests."""
    with _lock:
        return {
            k: (_writers.get(k, ""), v) for k, v in _stamps.items()
        }


def reset() -> None:
    """Clear the ledger (session start / tests)."""
    with _lock:
        _stamps.clear()
        _writers.clear()
