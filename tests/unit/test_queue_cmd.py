"""Tests for the queue CLI commands (Task 11.4)."""
import json

from click.testing import CliRunner

from eaccode.cli import main
from eaccode.orchestrator.queue import JobQueue


def _runner_with_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return CliRunner()


def _seed_job(tmp_path):
    from eaccode.config.paths import EaccodePaths

    q = JobQueue(EaccodePaths().data_dir / "queue.db")
    return __import__("asyncio").run(
        q.enqueue(name="review-bugs", prompt="check", workdir=str(tmp_path))
    )


def test_queue_status_shows_jobs(tmp_path, monkeypatch):
    runner = _runner_with_paths(tmp_path, monkeypatch)
    jid = _seed_job(tmp_path)
    result = runner.invoke(main, ["queue", "status"])
    assert result.exit_code == 0, result.output
    assert "review-bugs" in result.output
    assert "queued" in result.output


def test_queue_show_after_complete(tmp_path, monkeypatch):
    runner = _runner_with_paths(tmp_path, monkeypatch)
    jid = _seed_job(tmp_path)

    import asyncio
    from eaccode.config.paths import EaccodePaths

    q = JobQueue(EaccodePaths().data_dir / "queue.db")
    asyncio.run(q.complete(jid, report="all good", cost_usd=0.01))

    shown = runner.invoke(main, ["queue", "show", jid])
    assert shown.exit_code == 0, shown.output
    assert "all good" in shown.output


def test_queue_add_and_cancel(tmp_path, monkeypatch):
    runner = _runner_with_paths(tmp_path, monkeypatch)
    added = runner.invoke(main, ["queue", "add", "do something", "--name", "custom"])
    assert added.exit_code == 0, added.output
    # output: "✓ enqueued <uuid> (custom) — runs when a pool slot frees"
    jid = added.output.split()[2]

    cancelled = runner.invoke(main, ["queue", "cancel", jid])
    assert cancelled.exit_code == 0
    assert "cancelled" in cancelled.output.lower()


def test_review_requires_git_repo(tmp_path, monkeypatch):
    """Ohne git-Repo gibt es keinen Diff → saubere Meldung, keine Jobs."""
    monkeypatch.chdir(tmp_path)  # kein git-Repo → git diff liefert leeren stdout
    runner = _runner_with_paths(tmp_path, monkeypatch)
    result = runner.invoke(main, ["review"])
    assert result.exit_code == 0, result.output
    assert "No diff" in result.output
    assert "enqueued" not in result.output
