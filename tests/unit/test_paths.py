"""Tests für XDG-Pfad-Auflösung (Task 1.1)."""
from pathlib import Path

from eaccode.config.paths import EaccodePaths


def test_paths_resolve_to_user_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    paths = EaccodePaths()
    assert paths.config_dir == tmp_path / "config" / "eaccode"
    assert paths.data_dir == tmp_path / "data" / "eaccode"
    assert paths.cache_dir == tmp_path / "cache" / "eaccode"
    assert paths.sessions_dir == paths.data_dir / "sessions"
    assert paths.memory_dir == paths.data_dir / "memory"
    assert paths.skills_dir == paths.config_dir / "skills"


def test_paths_create_directories(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    paths = EaccodePaths()
    assert paths.config_dir.exists()
    assert paths.data_dir.exists()
    assert paths.sessions_dir.exists()
    assert paths.memory_dir.exists()


def test_providers_and_settings_files(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    paths = EaccodePaths()
    assert paths.providers_file == paths.config_dir / "providers.yaml"
    assert paths.settings_file == paths.config_dir / "eaccode.yaml"
