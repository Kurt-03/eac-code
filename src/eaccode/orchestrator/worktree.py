"""Worktree manager (Task 11.1) — isolated git worktrees per parallel agent."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class WorktreeManager:
    """Creates and removes isolated git worktrees for parallel agents."""

    def __init__(self, repo_root: Path, base_dir: Path | None = None) -> None:
        self.repo_root = repo_root
        self.base_dir = base_dir or (repo_root / ".eaccode" / "worktrees")

    def create(self, name: str) -> Path:
        target = self.base_dir / name
        subprocess.run(
            ["git", "-C", str(self.repo_root), "worktree", "add", "--detach", str(target)],
            check=True,
            capture_output=True,
        )
        return target

    def cleanup(self, name: str) -> None:
        target = self.base_dir / name
        if target.exists():
            subprocess.run(
                ["git", "-C", str(self.repo_root), "worktree", "remove", "--force", str(target)],
                check=True,
                capture_output=True,
            )

    def cleanup_all(self) -> None:
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir, ignore_errors=True)
