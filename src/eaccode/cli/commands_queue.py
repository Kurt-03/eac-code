"""CLI sub-commands — registered onto the main click group on import."""
from __future__ import annotations

from pathlib import Path

import click

from eaccode.cli import main
from eaccode.config.paths import EaccodePaths
from eaccode.config.settings import Settings

# ------------------------------------------------------------------- queue

@main.group()
def queue_cmd() -> None:
    """Manage the background job queue (parallel reviews, agents)."""


@queue_cmd.command("status")
def queue_status() -> None:
    """Show queue state: queued / running / done / failed."""
    import asyncio

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    queue = JobQueue(paths.data_dir / "queue.db", max_running=settings.max_parallel_agents)
    jobs = asyncio.run(queue.list_jobs(limit=30))
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j.status.value] = counts.get(j.status.value, 0) + 1
    click.echo(
        f"pool: max {settings.max_parallel_agents} concurrent  |  "
        + "  ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    )
    icons = {"queued": "⏳", "running": "▶", "done": "✓", "failed": "✗"}
    for j in jobs[:15]:
        click.echo(
            f"  {icons.get(j.status.value, '?')} {j.id[:8]}  {j.name:22s} "
            f"{j.status.value:7s} ${j.cost_usd:.3f}  {j.created_at[:19]}"
        )


@queue_cmd.command("show")
@click.argument("job_id")
def queue_show(job_id: str) -> None:
    """Show a job's full report."""
    import asyncio

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    queue = JobQueue(paths.data_dir / "queue.db")
    job = asyncio.run(queue.get(job_id))
    click.echo(f"# {job.name} ({job.status.value})\n")
    if job.report:
        click.echo(job.report)
    if job.error:
        click.echo(f"[error] {job.error}")


@queue_cmd.command("add")
@click.argument("prompt")
@click.option("--name", default="custom-job", help="Job name")
def queue_add(prompt: str, name: str) -> None:
    """Append an arbitrary agent job to the queue (runs when a slot frees)."""
    import asyncio

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    queue = JobQueue(paths.data_dir / "queue.db")
    job_id = asyncio.run(queue.enqueue(name=name, prompt=prompt, workdir=str(Path.cwd())))
    click.echo(f"✓ enqueued {job_id} ({name}) — runs when a pool slot frees")


@queue_cmd.command("cancel")
@click.argument("job_id")
def queue_cancel(job_id: str) -> None:
    """Cancel a queued (not yet running) job."""
    import asyncio

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    queue = JobQueue(paths.data_dir / "queue.db")
    ok = asyncio.run(queue.cancel(job_id))
    click.echo("✓ cancelled" if ok else "✗ job not found or already running")


@queue_cmd.command("prune")
def queue_prune() -> None:
    """Remove old done/failed jobs."""
    import asyncio

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    queue = JobQueue(paths.data_dir / "queue.db")
    jobs = asyncio.run(queue.list_jobs(limit=1000))
    removed = 0
    for j in jobs:
        if j.status.value in ("done", "failed"):
            import sqlite3

            with sqlite3.connect(queue.db_path) as conn:
                conn.execute("DELETE FROM jobs WHERE id=?", (j.id,))
            removed += 1
    click.echo(f"✓ pruned {removed} finished jobs")


# ------------------------------------------------------------------ review

@main.command("review")
@click.option("--diff", "diff_ref", default="HEAD", help="Diff ref (e.g. 'main...feature')")
@click.option("--aspects", default=None, help="Comma-separated: bugs,security,tests,style,perf")
@click.option("--detach", is_flag=True, help="Enqueue and return immediately")
def review_cmd(diff_ref: str, aspects: str | None, detach: bool) -> None:
    """Enqueue parallel code reviews of the current diff (one job per aspect).

    Jobs run in the shared pool (max `max_parallel_agents`, default 6).
    Watch progress with `eaccode queue status`; append more with --detach.
    """
    import asyncio
    import subprocess

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    try:
        diff = subprocess.run(
            ["git", "diff", diff_ref], capture_output=True, text=True, cwd=Path.cwd()
        ).stdout
    except FileNotFoundError:
        click.echo("Error: git is not installed or not a git repository.")
        return
    if not diff.strip():
        click.echo("No diff to review.")
        return

    default_aspects = ["bugs", "security", "tests"]
    chosen = (aspects or ",".join(default_aspects)).split(",")
    aspect_prompts = {
        "bugs": "Review this diff for logic errors, race conditions, and edge cases. "
                "Report concrete issues with line references.",
        "security": "Review this diff for security issues: injection, secrets, "
                    "authz flaws, unsafe deserialization.",
        "tests": "Review this diff for missing test coverage and suggest specific test cases.",
        "style": "Review this diff for style/consistency issues.",
        "perf": "Review this diff for performance problems (N+1, hot loops, allocations).",
    }

    queue = JobQueue(paths.data_dir / "queue.db", max_running=settings.max_parallel_agents)
    enqueued: list[str] = []
    for aspect in chosen:
        job_id = asyncio.run(queue.enqueue(
            name=f"review-{aspect}",
            prompt=(
                f"{aspect_prompts.get(aspect, 'Review this diff.').strip()}\n\n"
                f"DIFF TO REVIEW:\n```diff\n{diff[:50000]}\n```"
            ),
            workdir=str(Path.cwd()),
            tools=["read", "grep", "glob", "bash"],
            max_turns=15,
        ))
        enqueued.append(job_id)
        click.echo(f"✓ enqueued {job_id[:8]} review-{aspect}")

    if detach:
        click.echo(
            f"Jobs will run in the background pool (max {settings.max_parallel_agents} "
            f"concurrent). Watch with `eaccode queue status`."
        )
        return

    # Blocking mode: process the queue (including jobs from other terminals)
    # until all jobs we enqueued are finished. Each job runs in its own
    # isolated git worktree (Task 11.1).
    from eaccode.orchestrator.pool import WorkerPool, agent_runner, make_worktree_runner
    from eaccode.orchestrator.worktree import WorktreeManager

    async def _wait() -> None:
        runner = make_worktree_runner(WorktreeManager(Path.cwd()), agent_runner)
        pool = WorkerPool(queue, runner)
        while True:
            await pool.run_until_idle(wait_for_new=False)
            remaining = [
                j for j in await queue.list_jobs()
                if j.id in enqueued and j.status.value in ("queued", "running")
            ]
            if not remaining:
                return
            await asyncio.sleep(2)

    asyncio.run(_wait())
    click.echo("\nDone. Full reports: `eaccode queue show <job-id>`")


if __name__ == "__main__":
    main()
