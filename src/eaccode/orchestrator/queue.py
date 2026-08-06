"""Persistent job queue (Task 11.3) — SQLite, multi-process safe.

Jobs can be appended at any time from any terminal; the worker pool
claims them FIFO, never exceeding max_running (hard cap, default 6).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Job(BaseModel):
    id: str
    name: str
    prompt: str
    workdir: str
    tools: list[str] | None = None
    max_turns: int = 20
    status: JobStatus = JobStatus.QUEUED
    report: str | None = None
    error: str | None = None
    cost_usd: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class JobQueue:
    """SQLite-backed persistent queue. Safe for concurrent processes
    (each opens its own connection; WAL journal mode)."""

    def __init__(self, db_path: Path, max_running: int = 6) -> None:
        self.db_path = db_path
        self.max_running = max_running
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    workdir TEXT NOT NULL,
                    tools TEXT,
                    max_turns INTEGER NOT NULL DEFAULT 20,
                    status TEXT NOT NULL DEFAULT 'queued',
                    report TEXT,
                    error TEXT,
                    cost_usd REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    async def enqueue(
        self,
        name: str,
        prompt: str,
        workdir: str,
        tools: list[str] | None = None,
        max_turns: int = 20,
    ) -> str:
        job = Job(
            id=str(uuid.uuid4()),
            name=name,
            prompt=prompt,
            workdir=workdir,
            tools=tools,
            max_turns=max_turns,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, name, prompt, workdir, tools, max_turns, "
                "status, cost_usd, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    job.id,
                    job.name,
                    job.prompt,
                    job.workdir,
                    json.dumps(job.tools) if job.tools else None,
                    job.max_turns,
                    job.status.value,
                    job.cost_usd,
                    job.created_at,
                    job.updated_at,
                ),
            )
        return job.id

    async def claim_next(self) -> Job | None:
        """Atomically claim the oldest queued job if under the cap.

        BEGIN IMMEDIATE serializes concurrent claims from parallel workers
        (multiple processes / pool tasks), preventing double-claims.
        """
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                running = conn.execute(
                    "SELECT COUNT(*) AS n FROM jobs WHERE status='running'"
                ).fetchone()["n"]
                if running >= self.max_running:
                    conn.execute("ROLLBACK")
                    return None
                row = conn.execute(
                    "SELECT id FROM jobs WHERE status='queued' "
                    "ORDER BY created_at LIMIT 1"
                ).fetchone()
                if row is None:
                    conn.execute("ROLLBACK")
                    return None
                conn.execute(
                    "UPDATE jobs SET status='running', updated_at=? WHERE id=?",
                    (datetime.now().isoformat(), row["id"]),
                )
                full = conn.execute(
                    "SELECT * FROM jobs WHERE id=?", (row["id"],)
                ).fetchone()
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return self._row_to_job(full)

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            name=row["name"],
            prompt=row["prompt"],
            workdir=row["workdir"],
            tools=json.loads(row["tools"]) if row["tools"] else None,
            max_turns=row["max_turns"],
            status=JobStatus(row["status"]),
            report=row["report"],
            error=row["error"],
            cost_usd=row["cost_usd"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def complete(self, job_id: str, report: str, cost_usd: float = 0.0) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='done', report=?, cost_usd=?, updated_at=? WHERE id=?",
                (report, cost_usd, datetime.now().isoformat(), job_id),
            )

    async def fail(self, job_id: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='failed', error=?, updated_at=? WHERE id=?",
                (error, datetime.now().isoformat(), job_id),
            )

    async def get(self, job_id: str) -> Job:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._row_to_job(row)

    async def list_jobs(self, limit: int = 50) -> list[Job]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    async def cancel(self, job_id: str) -> bool:
        """Cancel a queued (not yet running) job."""
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE jobs SET status='failed', error='cancelled', updated_at=? "
                "WHERE id=? AND status='queued'",
                (datetime.now().isoformat(), job_id),
            )
            return cur.rowcount > 0
