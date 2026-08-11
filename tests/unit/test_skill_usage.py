"""Tests for skill usage tracking (P0.4, reduced) — local usage sidecars."""

from datetime import datetime, timedelta
from pathlib import Path

from eaccode.curator.curator import find_stale_skills
from eaccode.memory.skill_usage import (
    last_used_ts,
    read_usage,
    record_use,
    record_view,
)
from eaccode.memory.skills import discover_skills


def _skill_file(tmp_path, name: str = "demo.md") -> Path:
    p = tmp_path / name
    p.write_text(
        "---\nname: demo\ndescription: test skill\n---\nbody\n",
        encoding="utf-8",
    )
    return p


def test_read_missing_usage_is_empty(tmp_path):
    assert read_usage(_skill_file(tmp_path)) == {}


def test_record_use_counts_and_stamps(tmp_path):
    src = _skill_file(tmp_path)
    record_use(src)
    first_created = read_usage(src)["created_at"]
    record_use(src)
    data = read_usage(src)
    assert data["use_count"] == 2
    assert data["created_at"] == first_created  # set once, never moved
    assert isinstance(last_used_ts(src), float)


def test_record_view_separate_counter(tmp_path):
    src = _skill_file(tmp_path)
    record_view(src)
    record_view(src)
    record_use(src)
    data = read_usage(src)
    assert data["view_count"] == 2
    assert data["use_count"] == 1


def test_corrupt_usage_file_reads_empty(tmp_path):
    src = _skill_file(tmp_path)
    src.with_name("demo.usage.json").write_text("{not json", encoding="utf-8")
    assert read_usage(src) == {}
    assert last_used_ts(src) is None


def test_discover_prefers_usage_over_mtime(tmp_path):
    """A skill used recently must not look stale even if the file was
    edited long ago (mtime is the edit time, not the use time)."""
    src = _skill_file(tmp_path)
    # Old edit time...
    old = datetime.now() - timedelta(days=200)
    import os

    os.utime(src, (old.timestamp(), old.timestamp()))
    # ...but used today.
    record_use(src)

    skill = discover_skills([tmp_path])[0]
    assert skill.last_used > datetime.now() - timedelta(days=1)
    assert find_stale_skills([skill], stale_after_days=90) == []


def test_discover_falls_back_to_mtime_without_usage(tmp_path):
    src = _skill_file(tmp_path)
    old = datetime.now() - timedelta(days=200)
    import os

    os.utime(src, (old.timestamp(), old.timestamp()))
    skill = discover_skills([tmp_path])[0]
    assert skill.last_used < datetime.now() - timedelta(days=100)


def test_stale_detection_uses_usage_signal(tmp_path):
    """Curator integration: a skill untouched for 120 days is stale when
    its usage sidecar says so."""
    src = _skill_file(tmp_path)
    record_use(src)
    data = read_usage(src)
    data["last_used"] = (datetime.now() - timedelta(days=120)).timestamp()
    src.with_name("demo.usage.json").write_text(
        __import__("json").dumps(data), encoding="utf-8"
    )
    skill = discover_skills([tmp_path])[0]
    assert find_stale_skills([skill], stale_after_days=90) == [skill]
