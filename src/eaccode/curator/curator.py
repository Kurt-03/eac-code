"""Curator (Task 6.7 / C.5) — self-maintenance with a persisted lifecycle.

States per skill: ``active`` (used recently), ``stale`` (unused too
long), ``archived`` (explicitly shelved by the curator run) and
``pinned`` (usage-sidecar flag — protected from archiving). The curator
never deletes: it proposes archives, the user applies them.

The pause flag persists so a user can stop background curation runs.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

STALE_AFTER_DAYS = 90


def find_stale_skills(skills: list, stale_after_days: int = STALE_AFTER_DAYS) -> list:
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


class CuratorState:
    """Persisted curator lifecycle (C.5): pause flag + archived skills."""

    def __init__(self, state_file: Path | None = None) -> None:
        self.state_file = state_file
        self.paused = False
        self.archived: list[str] = []  # skill names
        self.load()

    def load(self) -> None:
        if self.state_file is None or not self.state_file.exists():
            return
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.paused = bool(data.get("paused", False))
            self.archived = [str(a) for a in data.get("archived", [])]
        except (OSError, ValueError):
            pass  # corrupt state → defaults

    def save(self) -> None:
        if self.state_file is None:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps({"paused": self.paused, "archived": self.archived}),
            encoding="utf-8",
        )
        tmp.replace(self.state_file)

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        self.save()

    def archive(self, skill_name: str) -> None:
        if skill_name not in self.archived:
            self.archived.append(skill_name)
            self.save()

    def unarchive(self, skill_name: str) -> None:
        if skill_name in self.archived:
            self.archived.remove(skill_name)
            self.save()

    def lifecycle_for(self, skill, stale_after_days: int = STALE_AFTER_DAYS) -> str:
        """active | stale | archived | pinned for one skill."""
        from eaccode.memory.skill_usage import is_pinned

        if is_pinned(skill.source):
            return "pinned"
        if skill.name in self.archived:
            return "archived"
        if find_stale_skills([skill], stale_after_days):
            return "stale"
        return "active"

    def propose_archive(self, skills: list,
                        stale_after_days: int = STALE_AFTER_DAYS) -> list:
        """Stale skills that are not already archived/pinned (proposals)."""
        from eaccode.memory.skill_usage import is_pinned

        return [
            s for s in skills
            if s.name not in self.archived
            and not is_pinned(s.source)
            and find_stale_skills([s], stale_after_days)
        ]
