"""Tests for the workspace block (Phase H.2)."""

import subprocess

from eaccode.agent.workspace import (
    build_coding_workspace_block,
    detect_project_facts,
)


def _init_git(tmp_path, branch="main"):
    """Initialize a git repo at tmp_path with one commit."""
    subprocess.run(["git", "init", "-q", "-b", branch, str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], check=True)


def test_workspace_block_outside_git_is_empty(tmp_path):
    assert build_coding_workspace_block(tmp_path) == ""


def test_workspace_block_shows_git_state(tmp_path):
    _init_git(tmp_path, branch="feature/x")
    block = build_coding_workspace_block(tmp_path)
    assert "Workspace" in block
    assert "feature/x" in block
    assert "Status: clean" in block
    assert "Recent commits:" in block


def test_workspace_block_shows_dirty_state(tmp_path):
    _init_git(tmp_path)
    (tmp_path / "new.txt").write_text("y", encoding="utf-8")
    block = build_coding_workspace_block(tmp_path)
    assert "1 untracked" in block  # Hermes format: "<count> <label>"


def test_project_facts_detect_verify_commands(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    facts = detect_project_facts(tmp_path)
    assert "pytest" in facts.verify_commands
    assert "pyproject.toml" in facts.manifests


def test_project_facts_detect_package_json(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"scripts": {"test": "vitest", "lint": "eslint"}}', encoding="utf-8"
    )
    facts = detect_project_facts(tmp_path)
    assert "npm run test" in facts.verify_commands
    assert "npm run lint" in facts.verify_commands
    assert facts.package_managers == []  # no lockfile → no pm detected


def test_project_facts_makefile(tmp_path):
    (tmp_path / "Makefile").write_text("test:\n\tpytest\nlint:\n\truff\n", encoding="utf-8")
    facts = detect_project_facts(tmp_path)
    assert "make test" in facts.verify_commands
    assert "make lint" in facts.verify_commands


def test_workspace_block_includes_verify_commands(tmp_path):
    _init_git(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    block = build_coding_workspace_block(tmp_path)
    assert "Verify: pytest" in block


def test_workspace_block_includes_context_files(tmp_path):
    _init_git(tmp_path)
    (tmp_path / "EACCODE.md").write_text("rules", encoding="utf-8")
    block = build_coding_workspace_block(tmp_path)
    assert "EACCODE.md" in block
