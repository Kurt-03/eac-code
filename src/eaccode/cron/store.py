"""Cron job store (Phase I.1) — SQLite-backed job persistence.

One table: id, name, schedule (cron expr or interval), prompt, skills,
script, enabled, repeat, next_run_at, last_run_at, last_status,
last_output, context_from, deliver, created_at, updated_at.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class CronJob:
    """One scheduled job."""

    id: str
    name: str
    schedule: str
    prompt: str = ""
    skills: list[str] = field(default_factory=list)
    script: str | None = None
    enabled: bool = True
    repeat: int | None = None  # None = forever
    next_run_at: str | None = None  # ISO
    last_run_at: str | None = None
    last_status: str = "never"
    last_output: str = ""
    context_from: list[str] = field(default_factory=list)
    deliver: str = "origin"
    no_agent: bool = False  # G.5: script-only watchdog jobs (no LLM)
    created_at: str = ""
    updated_at: str = ""


class JobStore:
    """SQLite store for cron jobs (thread-safe via per-call connections)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cron_jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    skills TEXT NOT NULL,
                    script TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    repeat INTEGER,
                    next_run_at TEXT,
                    last_run_at TEXT,
                    last_status TEXT NOT NULL DEFAULT 'never',
                    last_output TEXT NOT NULL DEFAULT '',
                    context_from TEXT NOT NULL DEFAULT '[]',
                    deliver TEXT NOT NULL DEFAULT 'origin',
                    no_agent INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # G.5: migration for databases created before `no_agent`.
            cols = {r[1] for r in conn.execute("PRAGMA table_info(cron_jobs)")}
            if "no_agent" not in cols:
                conn.execute(
                    "ALTER TABLE cron_jobs ADD COLUMN no_agent INTEGER "
                    "NOT NULL DEFAULT 0"
                )

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _row_to_job(self, row: sqlite3.Row) -> CronJob:
        return CronJob(
            id=row["id"], name=row["name"], schedule=row["schedule"],
            prompt=row["prompt"],
            skills=json.loads(row["skills"] or "[]"),
            script=row["script"], enabled=bool(row["enabled"]),
            repeat=row["repeat"], next_run_at=row["next_run_at"],
            last_run_at=row["last_run_at"], last_status=row["last_status"],
            last_output=row["last_output"],
            context_from=json.loads(row["context_from"] or "[]"),
            deliver=row["deliver"],
            no_agent=bool(row["no_agent"]) if "no_agent" in row.keys() else False,  # noqa: SIM118
            created_at=row["created_at"], updated_at=row["updated_at"],
        )
    # -------------------------------------------------------------- CRUD

    def create(self, job: CronJob) -> str:
        job.id = job.id or str(uuid.uuid4())[:8]
        now = self._now()
        job.created_at = job.created_at or now
        job.updated_at = now
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO cron_jobs (id, name, schedule, prompt, skills, script, "
                "enabled, repeat, next_run_at, last_run_at, last_status, last_output, "
                "context_from, deliver, no_agent, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (job.id, job.name, job.schedule, job.prompt,
                 json.dumps(job.skills), job.script, int(job.enabled),
                 job.repeat, job.next_run_at, job.last_run_at, job.last_status,
                 job.last_output, json.dumps(job.context_from), job.deliver,
                 int(job.no_agent), job.created_at, job.updated_at),
            )
        return job.id

    def get(self, job_id: str) -> CronJob | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM cron_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return self._row_to_job(row) if row else None

    def list(self, include_disabled: bool = True) -> list[CronJob]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if include_disabled:
                rows = conn.execute(
                    "SELECT * FROM cron_jobs ORDER BY created_at"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM cron_jobs WHERE enabled = 1 ORDER BY created_at"
                ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def update(self, job: CronJob) -> bool:
        job.updated_at = self._now()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE cron_jobs SET name=?, schedule=?, prompt=?, skills=?, "
                "script=?, enabled=?, repeat=?, next_run_at=?, last_run_at=?, "
                "last_status=?, last_output=?, context_from=?, deliver=?, "
                "no_agent=?, updated_at=? WHERE id=?",
                (job.name, job.schedule, job.prompt, json.dumps(job.skills),
                 job.script, int(job.enabled), job.repeat, job.next_run_at,
                 job.last_run_at, job.last_status, job.last_output,
                 json.dumps(job.context_from), job.deliver, int(job.no_agent),
                 job.updated_at, job.id),
            )
        return cur.rowcount > 0

    def set_enabled(self, job_id: str, enabled: bool) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE cron_jobs SET enabled=?, updated_at=? WHERE id=?",
                (int(enabled), self._now(), job_id),
            )
        return cur.rowcount > 0

    def delete(self, job_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM cron_jobs WHERE id=?", (job_id,))
        return cur.rowcount > 0

    def due_jobs(self, now_iso: str | None = None) -> list[CronJob]:
        """Enabled jobs whose next_run_at is due (or never scheduled)."""
        now_iso = now_iso or self._now()
        jobs = [j for j in self.list(include_disabled=False)
                if j.next_run_at is None or j.next_run_at <= now_iso]
        return jobs
