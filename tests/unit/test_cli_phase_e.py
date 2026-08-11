"""Tests for the E-phase CLI/config features."""

import os

import pytest

from eaccode.config.env_loader import load_dotenv_files
from eaccode.config.settings import Settings

# ---------------------------------------------------------------- E.6


def test_env_loader_sets_new_vars(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nFOO=bar\nEMPTY=\nQUOTED=\"x y\"\n", encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("QUOTED", raising=False)
    assert load_dotenv_files(env) == 2
    assert os.environ["FOO"] == "bar"
    assert os.environ["QUOTED"] == "x y"
    assert "EMPTY" not in os.environ


def test_env_loader_existing_env_wins(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FOO=fromfile\n", encoding="utf-8")
    monkeypatch.setenv("FOO", "fromshell")
    assert load_dotenv_files(env) == 0
    assert os.environ["FOO"] == "fromshell"


# ------------------------------------------------------------- E.4/E.5


def test_settings_migrates_auto_compact_threshold(tmp_path):
    f = tmp_path / "eaccode.yaml"
    f.write_text("auto_compact_threshold: 0.7\n", encoding="utf-8")
    settings = Settings.load(f)
    assert settings.compact_threshold == 0.7


def test_settings_corrupt_file_falls_back(tmp_path):
    f = tmp_path / "eaccode.yaml"
    f.write_text("permission_mode: [unclosed\n", encoding="utf-8")
    with pytest.warns(UserWarning):
        settings = Settings.load(f)
    assert settings.permission_mode.value == "default"
    assert not f.exists()  # moved aside as .broken
    assert f.with_suffix(".yaml.broken").exists()


def test_settings_invalid_value_falls_back(tmp_path):
    f = tmp_path / "eaccode.yaml"
    f.write_text("permission_mode: bogus-mode\n", encoding="utf-8")
    with pytest.warns(UserWarning):
        settings = Settings.load(f)
    assert settings.permission_mode.value == "default"
    assert f.exists()  # kept in place for inspection


def test_new_settings_sections():
    s = Settings()
    assert s.backup_keep_days == 7
    assert s.update_auto_check is False


# ------------------------------------------------------------ CLI smoke


def test_init_command(tmp_path, monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dat"))
    from eaccode.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    assert "✓" in result.output
    assert (tmp_path / "cfg" / "eaccode" / "eaccode.yaml").exists()
    assert (tmp_path / "cfg" / "eaccode" / "hooks" / "README.md").exists()


def test_version_command():
    from click.testing import CliRunner

    from eaccode.cli import main

    result = CliRunner().invoke(main, ["version"])
    assert result.exit_code == 0
    assert "eaccode" in result.output


def test_deps_command():
    from click.testing import CliRunner

    from eaccode.cli import main

    result = CliRunner().invoke(main, ["deps"])
    assert result.exit_code == 0
    assert "trafilatura" in result.output


def test_run_help_exists():  # E.9: oneshot verification
    from click.testing import CliRunner

    from eaccode.cli import main

    result = CliRunner().invoke(main, ["run", "--help"])
    assert result.exit_code == 0
    assert "headless" in result.output.lower() or "one" in result.output.lower()


def test_backup_commands(tmp_path, monkeypatch):
    from click.testing import CliRunner

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dat"))
    from eaccode.cli import main

    runner = CliRunner()
    assert runner.invoke(main, ["backup", "create"]).exit_code == 0
    result = runner.invoke(main, ["backup", "list"])
    assert result.exit_code == 0
    assert "eaccode-backup-" in result.output
