"""Tests for the remaining CLI commands (doctor, models, skills, config init)."""
from click.testing import CliRunner

from eaccode.cli import main


def _runner(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return CliRunner()


def test_doctor_reports_missing_providers(tmp_path, monkeypatch):
    runner = _runner(tmp_path, monkeypatch)
    result = runner.invoke(main, ["doctor"])
    assert "providers" in result.output
    assert "✗" in result.output  # keine Provider → Problem gemeldet


def test_doctor_ok_with_provider(tmp_path, monkeypatch):
    runner = _runner(tmp_path, monkeypatch)  # XDG-Pfade zuerst setzen!
    from eaccode.config.paths import EaccodePaths
    from eaccode.config.providers import ProviderConfig, save_providers

    save_providers(
        [ProviderConfig(name="minimax", api_key="k", model="MiniMax-M3")],
        EaccodePaths().providers_file,
    )
    result = runner.invoke(main, ["doctor"])
    assert "minimax" in result.output


def test_models_list(tmp_path, monkeypatch):
    runner = _runner(tmp_path, monkeypatch)  # XDG-Pfade zuerst setzen!
    from eaccode.config.paths import EaccodePaths
    from eaccode.config.providers import ProviderConfig, save_providers

    save_providers(
        [ProviderConfig(name="minimax", api_key="k", model="MiniMax-M3")],
        EaccodePaths().providers_file,
    )
    result = runner.invoke(main, ["models", "list"])
    assert result.exit_code == 0, result.output
    assert "minimax" in result.output
    assert "MiniMax-M3" in result.output


def test_skills_list_empty(tmp_path, monkeypatch):
    runner = _runner(tmp_path, monkeypatch)
    result = runner.invoke(main, ["skills", "list"])
    assert result.exit_code == 0
    assert "No skills" in result.output


def test_config_init_creates_template(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _runner(tmp_path, monkeypatch)
    result = runner.invoke(main, ["config", "init"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "EACCODE.md").exists()
    assert (tmp_path / ".eaccode").is_dir()
