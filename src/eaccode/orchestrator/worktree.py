"""Worktree manager — isolated git worktrees per parallel agent.

Git invocations go through bounded, non-interactive helpers (Phase A.4):
a private remote can never hang the queue on a credential prompt, and a
timeout can never leave suspended descendants holding captured pipes.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from eaccode._subprocess_compat import (
    IS_WINDOWS,
    noninteractive_git_env,
    windows_hide_flags,
)


def _git_run(args: list[str], *, timeout: float = 30.0) -> subprocess.CompletedProcess:
    """Run an internal git command fail-fast (never prompt, never hang)."""
    popen_kwargs: dict = {}
    if IS_WINDOWS:
        popen_kwargs["creationflags"] = windows_hide_flags()
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        env=noninteractive_git_env(),
        timeout=timeout,
        **popen_kwargs,
    )


class WorktreeManager:
    """Creates and removes isolated git worktrees for parallel agents."""

    def __init__(self, repo_root: Path, base_dir: Path | None = None) -> None:
        self.repo_root = repo_root
        self.base_dir = base_dir or (repo_root / ".eaccode" / "worktrees")

    def create(self, name: str) -> Path:
        target = self.base_dir / name
        result = _git_run(
            ["git", "-C", str(self.repo_root), "worktree", "add", "--detach", str(target)]
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git worktree add failed: {result.stderr.strip() or result.stdout.strip()}"
            )
        return target

    def cleanup(self, name: str) -> None:
        target = self.base_dir / name
        if target.exists():
            result = _git_run(
                ["git", "-C", str(self.repo_root), "worktree", "remove", "--force", str(target)]
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"git worktree remove failed: {result.stderr.strip() or result.stdout.strip()}"
                )

    def cleanup_all(self) -> None:
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir, ignore_errors=True)
