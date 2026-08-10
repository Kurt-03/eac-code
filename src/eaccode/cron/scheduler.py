"""Cron scheduler (Phase I.1) — due-job runner with interval/cron parsing.

Supports:
- intervals: "30m", "2h", "1d" (also "every 2h")
- cron expressions: "0 9 * * *" (5-field, via a compact parser)
- one-shot ISO timestamps
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from eaccode.cron.store import CronJob, JobStore

_INTERVAL_RE = re.compile(r"^(?:every\s+)?(\d+)\s*(s|m|h|d)$", re.IGNORECASE)
_CRON_RE = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$")

# Callable that executes one job: (job) -> (status, output)
JobRunner = Callable[[CronJob], Awaitable[tuple[str, str]]]


def parse_schedule(schedule: str, now: datetime | None = None) -> datetime | None:
    """Return the next run time for a schedule, or None (invalid)."""
    now = now or datetime.now()
    s = schedule.strip()

    m = _INTERVAL_RE.match(s)
    if m:
        unit = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}[m.group(2).lower()]
        return now + timedelta(**{unit: int(m.group(1))})

    # ISO one-shot timestamp
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass

    if _CRON_RE.match(s):
        return _next_cron(s, now)
    return None


def _next_cron(expr: str, now: datetime) -> datetime:
    """Next match of a 5-field cron expr (min hour dom mon dow)."""
    fields = expr.split()
    minutes = _cron_field(fields[0], 0, 59)
    hours = _cron_field(fields[1], 0, 23)
    doms = _cron_field(fields[2], 1, 31)
    months = _cron_field(fields[3], 1, 12)
    # Cron dow: 0=Sunday..6=Saturday; Python weekday(): 0=Monday..6=Sunday.
    dows = {6 if v == 0 else v - 1 for v in _cron_field(fields[4], 0, 6)}

    candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(60 * 24 * 366 * 2):  # look ahead up to 2 years
        if candidate.month not in months:
            candidate = (candidate.replace(day=1) + timedelta(days=32)).replace(
                day=1, hour=0, minute=0
            )
            continue
        if candidate.day not in doms:
            candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
            continue
        if candidate.weekday() not in dows:
            candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
            continue
        if candidate.hour not in hours:
            candidate = (candidate + timedelta(hours=1)).replace(minute=0)
            continue
        if candidate.minute not in minutes:
            candidate = candidate + timedelta(minutes=1)
            continue
        return candidate
    return now + timedelta(days=1)


def _cron_field(text: str, low: int, high: int) -> set[int]:
    """Parse one cron field: *, ranges (a-b), steps (a/b), lists (a,b)."""
    values: set[int] = set()
    for part in text.split(","):
        if part == "*":
            values.update(range(low, high + 1))
            continue
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            if base == "*":
                values.update(range(low, high + 1, step))
            else:
                lo, _, hi = base.partition("-")
                for v in range(int(lo), (int(hi) if hi else high) + 1, step):
                    values.add(v)
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            values.update(range(int(lo), int(hi) + 1))
            continue
        values.add(int(part))
    return {v for v in values if low <= v <= high}


class Scheduler:
    """Async scheduler loop: ticks every N seconds, runs due jobs."""

    def __init__(self, store: JobStore, runner: JobRunner, tick_seconds: float = 10.0) -> None:
        self.store = store
        self.runner = runner
        self.tick_seconds = tick_seconds
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    async def run_forever(self) -> None:
        """Tick loop until stop() is called."""
        while not self._stopped.is_set():
            await self.tick_once()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stopped.wait(), timeout=self.tick_seconds)

    async def tick_once(self) -> list[CronJob]:
        """Run all due jobs; returns the executed jobs."""
        executed: list[CronJob] = []
        for job in self.store.due_jobs():
            executed.append(job)
            await self._execute(job)
        return executed

    async def _execute(self, job: CronJob) -> None:
        from datetime import datetime

        job.last_run_at = datetime.now().isoformat(timespec="seconds")
        try:
            status, output = await self.runner(job)
        except Exception as e:
            status, output = "error", f"{type(e).__name__}: {e}"
        job.last_status = status
        job.last_output = output[:200_000]

        # Schedule the next run.
        if job.repeat is not None:
            job.repeat -= 1
            if job.repeat <= 0:
                job.enabled = False
        if job.enabled:
            nxt = parse_schedule(job.schedule)
            job.next_run_at = nxt.isoformat(timespec="seconds") if nxt else None
        self.store.update(job)

    def start(self) -> None:
        self._stopped = asyncio.Event()
        self._task = asyncio.create_task(self.run_forever())

    async def stop(self) -> None:
        self._stopped.set()
        if self._task:
            await self._task
            self._task = None
