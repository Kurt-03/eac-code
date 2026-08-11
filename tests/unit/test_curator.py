"""Tests for the curator (Task 6.7)."""
from datetime import datetime, timedelta

from eaccode.curator.curator import CuratorState, dedupe_memory, find_stale_skills


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


# ---------------------------------------------------------------- C.5


def _skill(tmp_path, name: str, days_old: int | None) -> object:
    from eaccode.memory.skills import Skill

    return Skill(
        name=name, description="x", content="y",
        source=tmp_path / f"{name}.md",
        last_used=(datetime.now() - timedelta(days=days_old)) if days_old else None,
    )


def test_state_pause_flag_roundtrip(tmp_path):
    state_file = tmp_path / "curator.json"
    state = CuratorState(state_file)
    assert state.paused is False
    state.set_paused(True)
    loaded = CuratorState(state_file)
    assert loaded.paused is True
    loaded.set_paused(False)
    assert CuratorState(state_file).paused is False


def test_archive_roundtrip(tmp_path):
    state = CuratorState(tmp_path / "curator.json")
    state.archive("old-skill")
    assert state.archived == ["old-skill"]
    state.unarchive("old-skill")
    assert state.archived == []


def test_lifecycle_labels(tmp_path):
    state = CuratorState(tmp_path / "curator.json")
    active = _skill(tmp_path, "active", 2)
    stale = _skill(tmp_path, "stale", 120)
    state.archive("archived-one")
    archived = _skill(tmp_path, "archived-one", 1)
    assert state.lifecycle_for(active) == "active"
    assert state.lifecycle_for(stale) == "stale"
    assert state.lifecycle_for(archived) == "archived"


def test_pinned_beats_stale(tmp_path):
    from eaccode.memory.skill_usage import set_pinned

    state = CuratorState(tmp_path / "curator.json")
    pinned = _skill(tmp_path, "keep", 200)
    set_pinned(pinned.source)
    assert state.lifecycle_for(pinned) == "pinned"
    assert state.propose_archive([pinned]) == []


def test_propose_archive_excludes_archived_and_pinned(tmp_path):
    from eaccode.memory.skill_usage import set_pinned

    state = CuratorState(tmp_path / "curator.json")
    stale1 = _skill(tmp_path, "s1", 120)
    stale2 = _skill(tmp_path, "s2", 120)
    pinned = _skill(tmp_path, "p1", 200)
    set_pinned(pinned.source)
    state.archive("s2")
    proposals = state.propose_archive([stale1, stale2, pinned])
    assert [s.name for s in proposals] == ["s1"]


def test_corrupt_state_file_falls_back(tmp_path):
    f = tmp_path / "curator.json"
    f.write_text("{broken", encoding="utf-8")
    state = CuratorState(f)
    assert state.paused is False
    assert state.archived == []
