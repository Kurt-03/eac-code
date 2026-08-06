"""Tests for the CLI skeleton (Task 1.4)."""
from click.testing import CliRunner

from eaccode.cli import main
from eaccode.config.settings import PermissionMode


def _runner_with_isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return CliRunner()


def test_cli_paths_shows_dirs(tmp_path, monkeypatch):
    runner = _runner_with_isolated_paths(tmp_path, monkeypatch)
    result = runner.invoke(main, ["paths"])
    assert result.exit_code == 0
    assert str(tmp_path / "config" / "eaccode") in result.output


def test_providers_add_and_list(tmp_path, monkeypatch):
    runner = _runner_with_isolated_paths(tmp_path, monkeypatch)
    result = runner.invoke(main, [
        "providers", "add",
        "--provider", "minimax",
        "--model", "MiniMax-M2",
        "--api-key", "mk-test-123",
    ])
    assert result.exit_code == 0, result.output
    assert "minimax" in result.output

    listed = runner.invoke(main, ["providers", "list"])
    assert listed.exit_code == 0
    assert "minimax" in listed.output
    assert "MiniMax-M2" in listed.output
    assert "mk-test-123" not in listed.output  # never show the key


def test_providers_add_prompts_for_key(tmp_path, monkeypatch):
    runner = _runner_with_isolated_paths(tmp_path, monkeypatch)
    result = runner.invoke(main, [
        "providers", "add",
        "--provider", "anthropic",
        "--model", "claude-sonnet-4-6",
    ], input="sk-secret\n")
    assert result.exit_code == 0, result.output


def test_providers_remove(tmp_path, monkeypatch):
    runner = _runner_with_isolated_paths(tmp_path, monkeypatch)
    runner.invoke(main, ["providers", "add", "--provider", "minimax",
                         "--model", "MiniMax-M2", "--api-key", "k"])
    result = runner.invoke(main, ["providers", "remove", "minimax"])
    assert result.exit_code == 0
    listed = runner.invoke(main, ["providers", "list"])
    assert "minimax" not in listed.output


def test_config_set_permission_mode(tmp_path, monkeypatch):
    runner = _runner_with_isolated_paths(tmp_path, monkeypatch)
    result = runner.invoke(main, ["config", "set", "permission_mode", "acceptEdits"])
    assert result.exit_code == 0, result.output

    shown = runner.invoke(main, ["config", "show"])
    assert shown.exit_code == 0
    assert "acceptEdits" in shown.output


def test_config_set_max_parallel_agents(tmp_path, monkeypatch):
    runner = _runner_with_isolated_paths(tmp_path, monkeypatch)
    result = runner.invoke(main, ["config", "set", "max_parallel_agents", "4"])
    assert result.exit_code == 0, result.output
    shown = runner.invoke(main, ["config", "show"])
    assert "4" in shown.output


def test_no_subcommand_shows_repl_hint(tmp_path, monkeypatch):
    runner = _runner_with_isolated_paths(tmp_path, monkeypatch)
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert "repl" in result.output.lower() or "phase 7" in result.output.lower()
