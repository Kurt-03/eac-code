"""Worker pool (Task 11.3) — processes the queue with a hard concurrency cap.

Picks up jobs appended by ANY process while running. Each job runs via
`eaccode run` (headless agent) in its own git worktree.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from eaccode.orchestrator.queue import Job, JobQueue


class WorkerPool:
    """Runs queued jobs in parallel with a hard concurrency cap.

    Spawns N worker tasks (default: all queue slots) that claim jobs
    concurrently — the cap lives in the queue (claim_next), so multiple
    pools/processes share the same global limit.
    """

    def __init__(
        self,
        queue: JobQueue,
        runner,
        poll_interval: float = 1.0,
        workers: int | None = None,
    ) -> None:
        self.queue = queue
        self.runner = runner
        self.poll_interval = poll_interval
        self.workers = workers or queue.max_running

    async def run_until_idle(self, wait_for_new: bool = False) -> None:
        """Process the queue until empty. wait_for_new keeps polling for
        jobs appended later (e.g. from another terminal)."""

        async def worker() -> None:
            while True:
                job = await self.queue.claim_next()
                if job is None:
                    if not wait_for_new:
                        return
                    await asyncio.sleep(self.poll_interval)
                    continue
                await self._run_job(job)

        await asyncio.gather(*(worker() for _ in range(self.workers)))

    async def _run_job(self, job: Job) -> None:
        try:
            report, cost = await self.runner(job, Path(job.workdir))
            await self.queue.complete(job.id, report, cost)
        except Exception as e:
            await self.queue.fail(job.id, str(e))


async def agent_runner(job: Job, workdir: Path) -> tuple[str, float]:
    """Run one headless agent (`eaccode run --print`) for a queued job."""
    import asyncio
    import json
    import subprocess

    cmd = [
        "eaccode", "run", job.prompt,
        "--print", "--output-format", "json",
        "--max-turns", str(job.max_turns),
    ]
    if job.tools:
        cmd += ["--allowed-tools", ",".join(job.tools)]
    # subprocess.run in a thread: asyncio subprocesses are unreliable on
    # Windows (errno 9 / NotImplementedError depending on the loop policy)
    proc = await asyncio.to_thread(
        subprocess.run,
        cmd,
        cwd=str(workdir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=3600,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or b"").decode()[:500])
    try:
        data = json.loads(proc.stdout.decode())
        return data.get("result", ""), data.get("cost_usd", 0.0)
    except Exception:
        return proc.stdout.decode(), 0.0


def make_worktree_runner(worktrees, runner):
    """Wrap a runner so each job executes in its own isolated git worktree
    (Task 11.1) — parallel reviews never touch the main tree. The worktree
    is always cleaned up, even on failure."""

    async def wrapped(job: Job, workdir: Path) -> tuple[str, float]:
        wt = worktrees.create(job.name)
        try:
            return await runner(job, wt)
        finally:
            worktrees.cleanup(job.name)

    return wrapped
