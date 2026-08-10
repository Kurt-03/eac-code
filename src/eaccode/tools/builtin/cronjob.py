"""cronjob tool (Phase I.1) — schedule recurring/one-shot agent jobs.

Actions: create | list | update | pause | resume | remove | run.
Schedules: intervals ("30m", "every 2h"), 5-field cron ("0 9 * * *"),
or ISO one-shot timestamps. Jobs persist in SQLite under
%LOCALAPPDATA%/eaccode/cron.db and are executed by the scheduler
(eaccode cron run) or the REPL's background worker.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from eaccode.cron.scheduler import parse_schedule
from eaccode.cron.store import CronJob, JobStore
from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


class CronjobInput(BaseModel):
    action: str = Field(description="create | list | update | pause | resume | remove | run")
    schedule: str = Field(default="", description="Interval (30m), cron ('0 9 * * *'), or ISO")
    prompt: str = Field(default="", description="Self-contained task for the job (create/update)")
    name: str = Field(default="", description="Human-friendly job name")
    job_id: str = Field(default="", description="Job id (update/pause/resume/remove/run)")
    script: str | None = Field(default=None, description="Path to a script the job runs")
    repeat: int | None = Field(default=None, description="Repeat count (None = forever)")
    skills: list[str] = Field(default_factory=list, description="Skills to load for the job")
    enabled_toolsets: list[str] = Field(default_factory=list, description="Toolset restriction")
    deliver: str = Field(default="origin", description="Delivery target")


class CronjobTool(Tool):
    name = "cronjob"
    tool_class = ToolClass.MUTATING
    description = (
        "Schedule recurring or one-shot agent jobs: create, list, update, "
        "pause, resume, remove, or run-now. Schedules: '30m', 'every 2h', "
        "'0 9 * * *' (cron), or an ISO timestamp for one-shot jobs."
    )
    input_model = CronjobInput
    requires_permission = True

    def __init__(self, store_path: Path | None = None) -> None:
        self._store = JobStore(store_path or Path())

    @property
    def store(self) -> JobStore:
        return self._store

    async def run(self, input: CronjobInput, ctx: ToolContext) -> ToolResult:
        action = input.action.lower()
        if action == "create":
            return self._create(input)
        if action == "list":
            return self._list()
        if action == "update":
            return self._update(input)
        if action == "pause":
            return self._set_enabled(input, False)
        if action == "resume":
            return self._set_enabled(input, True)
        if action == "remove":
            return self._remove(input)
        if action == "run":
            return await self._run_now(input)
        return ToolResult(content=f"Unknown action: {action}", is_error=True)

    # ------------------------------------------------------------- actions

    def _create(self, input: CronjobInput) -> ToolResult:
        if not input.schedule:
            return ToolResult(
                content="create requires a schedule ('30m', '0 9 * * *', ISO)",
                is_error=True,
            )
        if not input.prompt and not input.script:
            return ToolResult(content="create requires a prompt or a script", is_error=True)
        if parse_schedule(input.schedule) is None:
            return ToolResult(content=f"Invalid schedule: {input.schedule}", is_error=True)
        now = datetime.now().isoformat(timespec="seconds")
        nxt = parse_schedule(input.schedule)
        job = CronJob(
            id="", name=input.name or input.prompt[:40] or "job",
            schedule=input.schedule, prompt=input.prompt,
            script=input.script, skills=input.skills, repeat=input.repeat,
            next_run_at=nxt.isoformat(timespec="seconds") if nxt else None,
            deliver=input.deliver, created_at=now, updated_at=now,
        )
        job_id = self._store.create(job)
        return ToolResult(
            content=f"Created job '{job.name}' (id {job_id}) — next run "
                    f"{job.next_run_at or 'soon'}"
        )

    def _list(self) -> ToolResult:
        jobs = self._store.list()
        if not jobs:
            return ToolResult(content="No cron jobs.")
        lines = []
        for j in jobs:
            state = "enabled" if j.enabled else "PAUSED"
            lines.append(
                f"{j.id}: {j.name} [{state}] schedule={j.schedule} "
                f"last={j.last_status}"
            )
        return ToolResult(content="\n".join(lines))

    def _update(self, input: CronjobInput) -> ToolResult:
        if not input.job_id:
            return ToolResult(content="update requires a job_id", is_error=True)
        job = self._store.get(input.job_id)
        if job is None:
            return ToolResult(content=f"No job {input.job_id}", is_error=True)
        if input.schedule:
            if parse_schedule(input.schedule) is None:
                return ToolResult(content=f"Invalid schedule: {input.schedule}", is_error=True)
            job.schedule = input.schedule
            nxt = parse_schedule(input.schedule)
            job.next_run_at = nxt.isoformat(timespec="seconds") if nxt else None
        if input.prompt:
            job.prompt = input.prompt
        if input.name:
            job.name = input.name
        if input.script is not None:
            job.script = input.script
        if input.repeat is not None:
            job.repeat = input.repeat
        if input.skills:
            job.skills = input.skills
        if input.deliver:
            job.deliver = input.deliver
        self._store.update(job)
        return ToolResult(content=f"Updated job {job.id}")

    def _set_enabled(self, input: CronjobInput, enabled: bool) -> ToolResult:
        if not input.job_id:
            return ToolResult(content=f"{'resume' if enabled else 'pause'} requires a job_id",
                              is_error=True)
        if self._store.set_enabled(input.job_id, enabled):
            return ToolResult(
                content=f"{'Resumed' if enabled else 'Paused'} job {input.job_id}"
            )
        return ToolResult(content=f"No job {input.job_id}", is_error=True)

    def _remove(self, input: CronjobInput) -> ToolResult:
        if not input.job_id:
            return ToolResult(content="remove requires a job_id", is_error=True)
        if self._store.delete(input.job_id):
            return ToolResult(content=f"Removed job {input.job_id}")
        return ToolResult(content=f"No job {input.job_id}", is_error=True)

    async def _run_now(self, input: CronjobInput) -> ToolResult:
        if not input.job_id:
            return ToolResult(content="run requires a job_id", is_error=True)
        job = self._store.get(input.job_id)
        if job is None:
            return ToolResult(content=f"No job {input.job_id}", is_error=True)
        from eaccode.cron.scheduler import Scheduler

        scheduler = Scheduler(self._store, self._default_runner)
        await scheduler._execute(job)
        return ToolResult(
            content=f"Ran job {job.id}: {job.last_status}\n{job.last_output[:4000]}"
        )

    async def _default_runner(self, job: CronJob) -> tuple[str, str]:
        """Headless run via the CLI (works without a running REPL)."""
        import subprocess
        import sys

        try:
            cmd = [sys.executable, "-m", "eaccode", "run", "--print", "--prompt", job.prompt]
            if job.script:
                cmd += ["--script", job.script]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode == 0:
                return "success", proc.stdout.strip()[:50_000]
            return "error", (proc.stderr or proc.stdout).strip()[:50_000]
        except Exception as e:
            return "error", f"{type(e).__name__}: {e}"
