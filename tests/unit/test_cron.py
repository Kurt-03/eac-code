"""Tests for the cronjob toolset (Phase I.1) — store, scheduler, tool."""

from datetime import datetime

import pytest

from eaccode.cron.scheduler import Scheduler, parse_schedule
from eaccode.cron.store import CronJob, JobStore
from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.cronjob import CronjobInput, CronjobTool


@pytest.fixture
def store(tmp_path):
    return JobStore(tmp_path / "cron.db")


@pytest.fixture
def tool(tmp_path):
    return CronjobTool(store_path=tmp_path / "cron.db")


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path)


# ---------------------------------------------------------------- schedule

class TestSchedule:
    def test_interval_minutes(self):
        nxt = parse_schedule("30m")
        assert nxt is not None
        assert abs((nxt - datetime.now()).total_seconds() - 1800) < 5

    def test_interval_every_hours(self):
        nxt = parse_schedule("every 2h")
        assert nxt is not None
        assert abs((nxt - datetime.now()).total_seconds() - 7200) < 5

    def test_interval_days(self):
        nxt = parse_schedule("1d")
        assert abs((nxt - datetime.now()).total_seconds() - 86400) < 5

    def test_cron_daily(self):
        now = datetime(2026, 8, 9, 10, 0)
        nxt = parse_schedule("0 9 * * *", now=now)
        assert nxt == datetime(2026, 8, 10, 9, 0)

    def test_cron_weekly(self):
        now = datetime(2026, 8, 9, 10, 0)  # Sunday
        nxt = parse_schedule("0 9 * * 1", now=now)  # Monday
        assert nxt == datetime(2026, 8, 10, 9, 0)

    def test_iso_timestamp(self):
        nxt = parse_schedule("2026-12-24T08:00:00")
        assert nxt == datetime(2026, 12, 24, 8, 0)

    def test_invalid_returns_none(self):
        assert parse_schedule("garbage") is None
        assert parse_schedule("") is None


# ------------------------------------------------------------------ store

class TestStore:
    def test_create_get_list(self, store):
        jid = store.create(CronJob(
            id="", name="daily", schedule="0 9 * * *", prompt="run tests"
        ))
        job = store.get(jid)
        assert job.name == "daily"
        assert job.prompt == "run tests"
        assert store.list()[0].id == jid

    def test_update_and_enabled(self, store):
        jid = store.create(CronJob(id="", name="x", schedule="30m", prompt="p"))
        assert store.set_enabled(jid, False) is True
        assert store.get(jid).enabled is False
        job = store.get(jid)
        job.prompt = "new prompt"
        assert store.update(job) is True
        assert store.get(jid).prompt == "new prompt"

    def test_delete(self, store):
        jid = store.create(CronJob(id="", name="x", schedule="30m", prompt="p"))
        assert store.delete(jid) is True
        assert store.get(jid) is None

    def test_due_jobs(self, store):
        jid = store.create(CronJob(id="", name="due", schedule="30m", prompt="p",
                                   next_run_at="2020-01-01T00:00:00"))
        store.create(CronJob(id="", name="later", schedule="30m", prompt="p",
                             next_run_at="2999-01-01T00:00:00"))
        due = store.due_jobs()
        assert [j.id for j in due] == [jid]


# ------------------------------------------------------------------ tool

class TestTool:
    @pytest.mark.asyncio
    async def test_create_requires_schedule(self, tool, ctx):
        r = await tool.run(CronjobInput(action="create", prompt="x"), ctx)
        assert r.is_error is True

    @pytest.mark.asyncio
    async def test_create_requires_prompt_or_script(self, tool, ctx):
        r = await tool.run(CronjobInput(action="create", schedule="30m"), ctx)
        assert r.is_error is True

    @pytest.mark.asyncio
    async def test_create_cycle(self, tool, ctx):
        r = await tool.run(CronjobInput(
            action="create", schedule="30m", prompt="run pytest", name="tests"
        ), ctx)
        assert "Created job" in r.content
        job_id = r.content.split("id ")[1].split(")")[0]

        r = await tool.run(CronjobInput(action="list"), ctx)
        assert "tests" in r.content

        r = await tool.run(CronjobInput(action="pause", job_id=job_id), ctx)
        assert "Paused" in r.content
        r = await tool.run(CronjobInput(action="list"), ctx)
        assert "PAUSED" in r.content

        r = await tool.run(CronjobInput(action="resume", job_id=job_id), ctx)
        assert "Resumed" in r.content

        r = await tool.run(CronjobInput(action="remove", job_id=job_id), ctx)
        assert "Removed" in r.content
        r = await tool.run(CronjobInput(action="list"), ctx)
        assert "No cron jobs" in r.content

    @pytest.mark.asyncio
    async def test_invalid_schedule_rejected(self, tool, ctx):
        r = await tool.run(CronjobInput(
            action="create", schedule="not-a-schedule", prompt="x"
        ), ctx)
        assert r.is_error is True
        assert "Invalid schedule" in r.content

    @pytest.mark.asyncio
    async def test_unknown_action(self, tool, ctx):
        r = await tool.run(CronjobInput(action="frob"), ctx)
        assert r.is_error is True


# ------------------------------------------------------------- scheduler

class TestScheduler:
    @pytest.mark.asyncio
    async def test_tick_runs_due_jobs(self, store):
        jid = store.create(CronJob(
            id="", name="due", schedule="30m", prompt="p",
            next_run_at="2020-01-01T00:00:00",
        ))
        runs = []

        async def runner(job):
            runs.append(job.id)
            return "success", "output ok"

        sched = Scheduler(store, runner)
        executed = await sched.tick_once()
        assert [j.id for j in executed] == [jid]
        assert runs == [jid]
        job = store.get(jid)
        assert job.last_status == "success"
        assert job.last_output == "output ok"
        # Next run was scheduled.
        assert job.next_run_at is not None

    @pytest.mark.asyncio
    async def test_runner_error_captured(self, store):
        jid = store.create(CronJob(
            id="", name="bad", schedule="30m", prompt="p",
            next_run_at="2020-01-01T00:00:00",
        ))

        async def runner(job):
            raise RuntimeError("boom")

        sched = Scheduler(store, runner)
        await sched.tick_once()
        assert store.get(jid).last_status == "error"
        assert "boom" in store.get(jid).last_output

    @pytest.mark.asyncio
    async def test_repeat_count_disables_job(self, store):
        jid = store.create(CronJob(
            id="", name="once", schedule="30m", prompt="p",
            next_run_at="2020-01-01T00:00:00", repeat=1,
        ))

        async def runner(job):
            return "success", ""

        sched = Scheduler(store, runner)
        await sched.tick_once()
        job = store.get(jid)
        assert job.enabled is False  # repeat exhausted
        assert job.repeat == 0

    @pytest.mark.asyncio
    async def test_run_now_via_tool(self, tool, ctx):
        r = await tool.run(CronjobInput(
            action="create", schedule="30m", prompt="hello", name="h"
        ), ctx)
        job_id = r.content.split("id ")[1].split(")")[0]
        # _default_runner spawns the CLI; that would be slow/flaky in
        # tests, so inject a fast runner.
        async def fast_runner(job):
            return "success", "fast output"

        from eaccode.cron.scheduler import Scheduler

        sched = Scheduler(tool.store, fast_runner)
        job = tool.store.get(job_id)
        await sched._execute(job)
        assert tool.store.get(job_id).last_status == "success"
        assert tool.store.get(job_id).last_output == "fast output"
