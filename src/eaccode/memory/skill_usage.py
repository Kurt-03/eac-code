"""Skill usage tracking (P0.4, reduced) — local `<skill>.usage.json`.

The curator needs a real "last used" signal; without one it falls back
to the file mtime (last *edit*, not last *use*). Each skill markdown
file carries a small JSON sidecar updated atomically on use/view.

Pure local, best-effort: any IO problem is swallowed — usage data must
never break a skill load.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

_USAGE_SUFFIX = ".usage.json"


def _usage_path(source: Path) -> Path:
    return source.with_name(source.stem + _USAGE_SUFFIX)


def read_usage(source: Path) -> dict:
    """Current usage dict for a skill file ({} on missing/corrupt file)."""
    try:
        return json.loads(_usage_path(source).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_usage(source: Path, data: dict) -> None:
    path = _usage_path(source)
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)  # atomic on POSIX and Windows (same volume)
    except OSError:
        pass


def _touch(source: Path, key: str) -> None:
    data = read_usage(source)
    data[key] = data.get(key, 0) + 1
    data["last_used"] = time.time()
    data.setdefault("created_at", time.time())
    _write_usage(source, data)


def record_use(source: Path) -> None:
    """Count a skill use (injection into the agent context)."""
    _touch(source, "use_count")


def record_view(source: Path) -> None:
    """Count a skill view (listing/inspection by the user or agent)."""
    _touch(source, "view_count")


def last_used_ts(source: Path) -> float | None:
    """Epoch seconds of the last recorded use/view, else None."""
    ts = read_usage(source).get("last_used")
    return ts if isinstance(ts, (int, float)) else None
