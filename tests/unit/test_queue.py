"""Tests for the persistent job queue (Task 11.3)."""
import pytest

from eaccode.orchestrator.queue import JobQueue, JobStatus


@pytest.mark.asyncio
async def test_enqueue_and_claim(tmp_path):
    q = JobQueue(tmp_path / "jobs.db")
    job_id = await q.enqueue(name="review-bugs", prompt="check bugs", workdir="/tmp")
    assert job_id is not None
    claimed = await q.claim_next()
    assert claimed is not None
    assert claimed.name == "review-bugs"
    assert claimed.status == JobStatus.RUNNING
    assert await q.claim_next() is None  # nur ein Job, schon running


@pytest.mark.asyncio
async def test_append_while_running(tmp_path):
    """Jobs die während des Laufs ankommen, werden FIFO aufgehoben."""
    q = JobQueue(tmp_path / "jobs.db")
    await q.enqueue(name="job-1", prompt="a", workdir="/tmp")
    await q.enqueue(name="job-2", prompt="b", workdir="/tmp")
    await q.claim_next()  # job-1 läuft
    await q.enqueue(name="job-3", prompt="c", workdir="/tmp")
    assert (await q.claim_next()).name == "job-2"
    assert (await q.claim_next()).name == "job-3"
    assert await q.claim_next() is None


@pytest.mark.asyncio
async def test_complete_and_fail(tmp_path):
    q = JobQueue(tmp_path / "jobs.db")
    await q.enqueue(name="job-1", prompt="a", workdir="/tmp")
    claimed = await q.claim_next()
    await q.complete(claimed.id, report="all good", cost_usd=0.12)
    done = await q.get(claimed.id)
    assert done.status == JobStatus.DONE
    assert done.report == "all good"

    await q.enqueue(name="job-2", prompt="b", workdir="/tmp")
    c2 = await q.claim_next()
    await q.fail(c2.id, error="agent crashed")
    f = await q.get(c2.id)
    assert f.status == JobStatus.FAILED
    assert "crashed" in f.error


@pytest.mark.asyncio
async def test_claim_respects_concurrency_cap(tmp_path):
    """Claim darf nie mehr als max_running Jobs rausgeben."""
    q = JobQueue(tmp_path / "jobs.db", max_running=6)
    for i in range(8):
        await q.enqueue(name=f"j{i}", prompt="x", workdir="/tmp")
    claimed = [await q.claim_next() for _ in range(10)]
    running = [c for c in claimed if c is not None]
    assert len(running) == 6  # harter Cap


@pytest.mark.asyncio
async def test_cancel_queued_job(tmp_path):
    q = JobQueue(tmp_path / "jobs.db")
    jid = await q.enqueue(name="j", prompt="x", workdir="/tmp")
    assert await q.cancel(jid) is True
    assert (await q.get(jid)).status == JobStatus.FAILED
    # bereits laufende Jobs kann man nicht cancanceln
    jid2 = await q.enqueue(name="j2", prompt="x", workdir="/tmp")
    await q.claim_next()
    assert await q.cancel(jid2) is False


@pytest.mark.asyncio
async def test_list_jobs_newest_first(tmp_path):
    q = JobQueue(tmp_path / "jobs.db")
    await q.enqueue(name="a", prompt="x", workdir="/tmp")
    await q.enqueue(name="b", prompt="x", workdir="/tmp")
    jobs = await q.list_jobs()
    assert [j.name for j in jobs] == ["b", "a"]
