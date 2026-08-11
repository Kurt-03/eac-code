"""Tests for G-phase features (G.1/G.2/G.3/G.5/G.6)."""

import os

import pytest

from eaccode.tools.daemon_pool import DaemonPool
from eaccode.tools.process_registry import kill_all, list_processes, register


def test_process_registry_register_and_list():
    register(12345, "echo hi")
    assert any(p.pid == 12345 and p.command == "echo hi"
               for p in list_processes())


def test_process_registry_kill_all_safe():
    # A dead pid: kill fails silently, nothing crashes.
    register(99999999, "ghost")
    killed = kill_all()
    assert killed == 0


def test_daemon_pool_add_and_list():
    pool = DaemonPool(slots=2)
    assert pool.add("web", 99991, "npm run dev") is None
    assert pool.list()[0].key == "web"


def test_daemon_pool_full():
    pool = DaemonPool(slots=1)
    pool.add("a", 99991, "x")
    error = pool.add("b", 99992, "y")
    assert error is not None
    assert "full" in error


def test_daemon_pool_stop_all():
    pool = DaemonPool(slots=2)
    pool.add("a", 99993, "x")
    pool.add("b", 99994, "y")
    # Unknown pids: kill fails silently, but the pool still clears.
    assert pool.stop_all() >= 0
    assert pool.list() == []


# ---------------------------------------------------------------- G.1


def test_process_pty_rejected_on_windows(monkeypatch):
    from eaccode.tools.builtin import process as process_mod

    monkeypatch.setattr(process_mod, "IS_WINDOWS", True)
    reg = process_mod._ProcessRegistry()
    with pytest.raises(ValueError, match="PTY"):
        reg.spawn("k", "echo hi", pty=True)


def test_process_pty_allowed_on_posix(monkeypatch):
    if os.name == "nt":
        pytest.skip("POSIX-only behavior")
    from eaccode.tools.builtin import process as process_mod

    monkeypatch.setattr(process_mod, "IS_WINDOWS", False)
    reg = process_mod._ProcessRegistry()
    managed = reg.spawn("k", "echo hi", pty=True)
    try:
        assert managed.pid > 0
    finally:
        reg.kill("k")


# ---------------------------------------------------------------- G.5


def test_cron_no_agent_requires_script(tmp_path):
    import asyncio

    from eaccode.tools.base import ToolContext
    from eaccode.tools.builtin.cronjob import CronjobInput, CronjobTool

    tool = CronjobTool(store_path=tmp_path / "cron.db")
    ctx = ToolContext(workdir=tmp_path)
    result = asyncio.run(tool.run(
        CronjobInput(action="create", schedule="30m", script="x.py",
                     no_agent=True), ctx,
    ))
    assert result.is_error is False  # script present → ok
    result2 = asyncio.run(tool.run(
        CronjobInput(action="create", schedule="30m", prompt="p",
                     no_agent=True), ctx,
    ))
    assert result2.is_error is True
    assert "script" in result2.content


def test_cron_no_agent_runner_skips_llm(tmp_path):
    import asyncio

    from eaccode.cron.store import CronJob
    from eaccode.tools.builtin.cronjob import CronjobTool

    tool = CronjobTool(store_path=tmp_path / "cron.db")
    script = tmp_path / "watch.py"
    script.write_text("print('WATCHDOG_OK')", encoding="utf-8")
    job = CronJob(id="j1", name="watch", schedule="30m",
                  script=str(script), no_agent=True)
    status, output = asyncio.run(tool._default_runner(job))
    assert status == "success"
    assert "WATCHDOG_OK" in output


def test_cron_no_agent_runner_requires_script(tmp_path):
    import asyncio

    from eaccode.cron.store import CronJob
    from eaccode.tools.builtin.cronjob import CronjobTool

    tool = CronjobTool(store_path=tmp_path / "cron.db")
    job = CronJob(id="j2", name="bad", schedule="30m", no_agent=True)
    status, output = asyncio.run(tool._default_runner(job))
    assert status == "error"
    assert "script" in output


def test_cron_store_no_agent_roundtrip(tmp_path):
    from eaccode.cron.store import CronJob, JobStore

    store = JobStore(tmp_path / "cron.db")
    job = CronJob(id="j3", name="w", schedule="30m", script="s.py",
                  no_agent=True)
    store.create(job)
    loaded = store.get("j3")
    assert loaded.no_agent is True
    loaded.no_agent = False
    store.update(loaded)
    assert store.get("j3").no_agent is False


# ---------------------------------------------------------------- G.7


@pytest.mark.asyncio
async def test_heartbeat_fires_periodically():
    import asyncio

    from eaccode.agent.heartbeat import Heartbeat

    beats = []
    heartbeat = Heartbeat(0.05, lambda: beats.append(1))
    heartbeat.start()
    try:
        await asyncio.sleep(0.18)
    finally:
        heartbeat.stop()
    assert len(beats) >= 2


@pytest.mark.asyncio
async def test_heartbeat_stop_halts():
    import asyncio

    from eaccode.agent.heartbeat import Heartbeat

    beats = []
    heartbeat = Heartbeat(0.02, lambda: beats.append(1))
    heartbeat.start()
    await asyncio.sleep(0.08)
    heartbeat.stop()
    count = len(beats)
    await asyncio.sleep(0.08)
    assert len(beats) == count  # no beats after stop


def test_cron_store_migration_adds_no_agent(tmp_path):
    import sqlite3

    from eaccode.cron.store import JobStore

    db = tmp_path / "cron.db"
    # Simulate a pre-no_agent database.
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE cron_jobs ("
            "id TEXT PRIMARY KEY, name TEXT NOT NULL, schedule TEXT NOT NULL, "
            "prompt TEXT NOT NULL, skills TEXT NOT NULL, script TEXT, "
            "enabled INTEGER NOT NULL DEFAULT 1, repeat INTEGER, "
            "next_run_at TEXT, last_run_at TEXT, "
            "last_status TEXT NOT NULL DEFAULT 'never', "
            "last_output TEXT NOT NULL DEFAULT '', "
            "context_from TEXT NOT NULL DEFAULT '[]', "
            "deliver TEXT NOT NULL DEFAULT 'origin', "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
    store = JobStore(db)  # _init_db must ALTER the table
    cols = {r[1] for r in sqlite3.connect(db).execute(
        "PRAGMA table_info(cron_jobs)")}
    assert "no_agent" in cols
    del store
