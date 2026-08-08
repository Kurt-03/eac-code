"""Tests for file safety (Phase A.1)."""

from eaccode.tools.safety import (
    is_read_blocked,
    is_write_denied,
    read_blocked_error,
    write_denied_error,
)


def test_write_denied_inside_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    from eaccode.config.paths import EaccodePaths

    target = EaccodePaths().config_dir / "providers.yaml"
    assert is_write_denied(target) is not None
    assert "Write denied" in write_denied_error(target)


def test_write_denied_inside_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    from eaccode.config.paths import EaccodePaths

    assert is_write_denied(EaccodePaths().sessions_dir / "sessions.db") is not None


def test_write_allowed_in_workdir(tmp_path):
    assert is_write_denied(tmp_path / "main.py") is None
    assert write_denied_error(tmp_path / "main.py") == ""


def test_read_blocked_credential_files(tmp_path):
    assert is_read_blocked(tmp_path / ".env")
    assert is_read_blocked(tmp_path / "providers.yaml")
    assert is_read_blocked(tmp_path / "deploy" / ".env")
    assert is_read_blocked(tmp_path / "id_rsa.pem")
    assert is_read_blocked(tmp_path / "api-key.txt")
    assert "Read blocked" in read_blocked_error(tmp_path / ".env")


def test_read_allowed_normal_files(tmp_path):
    assert is_read_blocked(tmp_path / "main.py") is False
    assert is_read_blocked(tmp_path / "src" / "providers.py") is False
    assert is_read_blocked(tmp_path / "keyboard.md") is False
    assert read_blocked_error(tmp_path / "main.py") == ""


def test_read_blocked_uppercase_env(tmp_path):
    assert is_read_blocked(tmp_path / ".ENV")
