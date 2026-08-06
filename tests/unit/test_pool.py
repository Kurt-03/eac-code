"""Tests for the worker pool (Task 11.3) — cap + scaling."""
import time

import pytest

from eaccode.orchestrator.pool import WorkerPool
from eaccode.orchestrator.queue import JobQueue, JobStatus


async def slow_runner(job, workdir):
    await asyncio.sleep(1.0)  # simulate API latency
    return f"## {job.name}\ndone", 0.01


import asyncio  # noqa: E402


@pytest.mark.asyncio
async def test_pool_cap_and_scaling(tmp_path):
    queue = JobQueue(tmp_path / "jobs.db", max_running=6)
    for i in range(12):
        await queue.enqueue(name=f"j{i}", prompt="x", workdir=str(tmp_path))
    pool = WorkerPool(queue, slow_runner)
    t0 = time.monotonic()
    await pool.run_until_idle()
    elapsed = time.monotonic() - t0
    assert elapsed < 4.0  # 2 Wellen à 6 × 1s, nicht 12s
    jobs = await queue.list_jobs(limit=20)
    assert all(j.status == JobStatus.DONE for j in jobs)


@pytest.mark.asyncio
async def test_failed_job_marked_failed(tmp_path):
    async def failing_runner(job, workdir):
        raise RuntimeError("boom")

    queue = JobQueue(tmp_path / "jobs.db", max_running=6)
    await queue.enqueue(name="f", prompt="x", workdir=str(tmp_path))
    pool = WorkerPool(queue, failing_runner)
    await pool.run_until_idle()
    job = (await queue.list_jobs())[0]
    assert job.status == JobStatus.FAILED
    assert "boom" in job.error
