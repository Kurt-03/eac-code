"""Curator (Task 6.7) — self-maintenance: stale skills, memory dedupe.

Like the Hermes curator: reports stale skills as proposals (never deletes
automatically), dedupes memory facts automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CuratorSettings:
    enabled: bool = True
    interval_hours: int = 24
    stale_after_days: int = 90


def find_stale_skills(skills: list, stale_after_days: int = 90) -> list:
    """Skills not used for longer than stale_after_days (never-used = not stale)."""
    cutoff = datetime.now() - timedelta(days=stale_after_days)
    return [
        s for s in skills
        if s.last_used is not None and s.last_used < cutoff
    ]


def dedupe_memory(facts: list[str]) -> list[str]:
    """Remove exact duplicates (normalized compare, first occurrence wins)."""
    seen: dict[str, str] = {}
    for f in facts:
        key = " ".join(f.lower().split())  # normalize: case + whitespace
        seen.setdefault(key, f)
    return list(seen.values())
