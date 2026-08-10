"""eaccode cron — scheduler daemon + job management CLI (Phase I.1)."""

from __future__ import annotations

import asyncio

import click

from eaccode.config.paths import EaccodePaths
from eaccode.cron.scheduler import Scheduler
from eaccode.cron.store import JobStore


@click.group("cron")
def cron_group() -> None:
    """Scheduled agent jobs."""


@cron_group.command("run")
@click.option("--once", is_flag=True, default=False, help="Run due jobs once and exit")
@click.option("--tick", default=10.0, help="Tick interval in seconds (default 10)")
def cron_run(once: bool, tick: float) -> None:
    """Run the scheduler: execute due jobs (daemon by default)."""
    from eaccode.tools.builtin.cronjob import CronjobTool

    paths = EaccodePaths()
    store = JobStore(paths.cron_db)
    tool = CronjobTool(store_path=paths.cron_db)
    runner = tool._default_runner  # headless CLI runner (no REPL needed)

    async def _run() -> None:
        sched = Scheduler(store, runner, tick_seconds=tick)
        if once:
            executed = await sched.tick_once()
            for job in executed:
                click.echo(f"{job.id}: {job.last_status}")
        else:
            click.echo(f"eaccode cron: watching {paths.cron_db} "
                       f"(tick {tick}s, Ctrl+C to stop)")
            await sched.run_forever()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        click.echo("\nStopped.")


@cron_group.command("list")
def cron_list() -> None:
    """List all scheduled jobs."""
    paths = EaccodePaths()
    store = JobStore(paths.cron_db)
    jobs = store.list()
    if not jobs:
        click.echo("No cron jobs. Create one in the REPL with the cronjob tool.")
        return
    for j in jobs:
        state = "enabled" if j.enabled else "PAUSED"
        click.echo(
            f"{j.id}: {j.name} [{state}] schedule={j.schedule} "
            f"last={j.last_status}"
        )


@cron_group.command("clear")
@click.confirmation_option(prompt="Delete ALL cron jobs?")
def cron_clear() -> None:
    """Delete every scheduled job."""
    paths = EaccodePaths()
    store = JobStore(paths.cron_db)
    for job in store.list():
        store.delete(job.id)
    click.echo("All cron jobs removed.")
