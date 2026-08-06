"""Tests for the curator (Task 6.7)."""
from datetime import datetime, timedelta

from eaccode.curator.curator import dedupe_memory, find_stale_skills


def test_stale_skill_detection(tmp_path):
    from eaccode.memory.skills import Skill

    old = Skill(
        name="old", description="x", content="y", source=tmp_path / "old.md",
        last_used=datetime.now() - timedelta(days=120),
    )
    fresh = Skill(
        name="fresh", description="x", content="y", source=tmp_path / "fresh.md",
        last_used=datetime.now() - timedelta(days=2),
    )
    never = Skill(
        name="never", description="x", content="y", source=tmp_path / "never.md",
        last_used=None,
    )
    stale = find_stale_skills([old, fresh, never], stale_after_days=90)
    assert [s.name for s in stale] == ["old"]  # never-used ist nicht stale


def test_memory_dedupe():
    facts = ["Build nutzt uv", "Build nutzt uv", "Tests: pytest", "Build nutzt uv (2026)"]
    deduped = dedupe_memory(facts)
    assert len(deduped) == 3  # exakte Duplikate raus, ähnliche bleiben
    assert deduped.count("Build nutzt uv") == 1
