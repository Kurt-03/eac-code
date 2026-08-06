"""Tests for the worktree manager (Task 11.1)."""
import subprocess

import pytest

from eaccode.orchestrator.worktree import WorktreeManager


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.txt").write_text("v1")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    return tmp_path


def test_create_and_cleanup_worktree(repo):
    mgr = WorktreeManager(repo)
    wt = mgr.create("review-1")
    assert wt.exists()
    assert (wt / "f.txt").exists()  # isolated copy
    mgr.cleanup("review-1")
    assert not wt.exists()


def test_worktree_isolation(repo):
    mgr = WorktreeManager(repo)
    wt = mgr.create("review-2")
    (wt / "new.txt").write_text("x")
    assert not (repo / "new.txt").exists()  # main tree untouched
    mgr.cleanup("review-2")


def test_cleanup_all(repo):
    mgr = WorktreeManager(repo)
    mgr.create("a")
    mgr.create("b")
    mgr.cleanup_all()
    assert not mgr.base_dir.exists()
