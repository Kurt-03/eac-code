"""Tests for skill triggers + pre-filter (A.6)."""

from datetime import datetime, timedelta
from pathlib import Path

from eaccode.memory.skill_triggers import (
    build_skill_index,
    fuzzy_match,
    match_triggers,
    select_skills_for_turn,
)
from eaccode.memory.skills import Skill


def _skill(name: str, triggers: list[str], last_used: datetime | None = None) -> Skill:
    return Skill(
        name=name, description=f"d-{name}", content="body",
        source=Path(f"/tmp/{name}.md"), triggers=triggers, last_used=last_used,
    )


def test_match_triggers_finds_keyword():
    skills = [_skill("pytest", ["pytest"]), _skill("git", ["git", "commit"])]
    hits = match_triggers(skills, "bitte pytest laufen lassen")
    assert [s.name for s in hits] == ["pytest"]


def test_match_triggers_case_insensitive():
    skills = [_skill("docker", ["docker"])]
    assert match_triggers(skills, "Docker build") == skills


def test_match_triggers_no_hit():
    skills = [_skill("git", ["git"])]
    assert match_triggers(skills, "wie ist das wetter") == []


def test_fuzzy_match_finds_close_name():
    assert fuzzy_match("pytest", ["pytests", "git"]) == "pytests"
    assert fuzzy_match("unrelated", ["git", "docker"]) is None


def test_select_prefers_triggered_then_recent():
    now = datetime.now()
    old = _skill("old", [], last_used=now - timedelta(days=30))
    recent = _skill("recent", [], last_used=now)
    triggered = _skill("hot", ["hot"], last_used=now - timedelta(days=90))
    selected = select_skills_for_turn([old, recent, triggered], "hot topic")
    assert selected[0].name == "hot"  # trigger wins
    assert "recent" in [s.name for s in selected]


def test_select_caps_at_max():
    skills = [_skill(f"s{i}", [f"k{i}"], last_used=datetime.now()) for i in range(12)]
    selected = select_skills_for_turn(skills, "k0 k1 k2 k3 k4 k5 k6 k7", max_inject=4)
    assert len(selected) == 4
    assert selected[0].name == "s0"


def test_build_index_compact():
    index = build_skill_index([_skill("a", []), _skill("b", [])])
    assert "a" in index and "b" in index
    assert "body" not in index  # index has no content
    assert build_skill_index([]) == ""
