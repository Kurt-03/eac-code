"""Tests for the settings model (Task 1.3)."""
import pytest

from eaccode.config.settings import CuratorSettings, PermissionMode, Settings


def test_default_settings():
    s = Settings()
    assert s.default_provider == "anthropic"
    assert s.permission_mode == PermissionMode.DEFAULT
    assert s.max_turns == 50
    assert s.max_parallel_agents == 6
    assert s.show_reasoning is True
    assert s.curator.enabled is True
    assert s.curator.stale_after_days == 90


def test_settings_yaml_roundtrip(tmp_path):
    s = Settings(max_turns=10, default_provider="minimax", permission_mode=PermissionMode.ACCEPT_EDITS)
    file = tmp_path / "eaccode.yaml"
    s.save(file)
    loaded = Settings.load(file)
    assert loaded.max_turns == 10
    assert loaded.default_provider == "minimax"
    assert loaded.permission_mode == PermissionMode.ACCEPT_EDITS


def test_load_missing_file_returns_defaults(tmp_path):
    assert Settings.load(tmp_path / "missing.yaml") == Settings()


def test_permission_mode_enum_values():
    assert {m.value for m in PermissionMode} == {
        "default",
        "acceptEdits",
        "plan",
        "bypassPermissions",
    }


def test_max_parallel_agents_validated():
    with pytest.raises(ValueError):
        Settings(max_parallel_agents=0)  # must be >= 1


def test_curator_settings_roundtrip(tmp_path):
    s = Settings(curator=CuratorSettings(interval_hours=48, stale_after_days=30))
    file = tmp_path / "eaccode.yaml"
    s.save(file)
    loaded = Settings.load(file)
    assert loaded.curator.interval_hours == 48
    assert loaded.curator.stale_after_days == 30
