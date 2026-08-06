"""Tests for the agent skill tools (Task 6.5)."""
from pathlib import Path

import pytest

from eaccode.memory.skill_tools import (
    SkillCreateInput,
    SkillCreateTool,
    SkillListInput,
    SkillListTool,
    SkillPatchInput,
    SkillPatchTool,
)
from eaccode.tools.base import ToolContext


@pytest.fixture
def skills_dir(tmp_path):
    d = tmp_path / "skills"
    d.mkdir()
    return d


@pytest.mark.asyncio
async def test_agent_creates_skill(skills_dir):
    tool = SkillCreateTool()
    ctx = ToolContext(workdir=Path("/tmp"), skills_dir=skills_dir)
    result = await tool.run(
        SkillCreateInput(
            name="git-workflow",
            description="Use when working with git repos",
            content="1. Always run `git status` first\n2. Commit after each task",
        ),
        ctx,
    )
    assert result.is_error is False
    assert (skills_dir / "git-workflow.md").exists()
    saved = (skills_dir / "git-workflow.md").read_text()
    assert "name: git-workflow" in saved  # frontmatter
    assert "git status" in saved


@pytest.mark.asyncio
async def test_agent_patches_skill_immediately(skills_dir):
    (skills_dir / "git-workflow.md").write_text(
        "---\nname: git-workflow\ndescription: x\n---\nold steps"
    )
    tool = SkillPatchTool()
    ctx = ToolContext(workdir=Path("/tmp"), skills_dir=skills_dir)
    result = await tool.run(
        SkillPatchInput(
            name="git-workflow",
            old_string="old steps",
            new_string="new steps with pitfall: never use --force",
        ),
        ctx,
    )
    assert result.is_error is False
    assert "never use --force" in (skills_dir / "git-workflow.md").read_text()


@pytest.mark.asyncio
async def test_skill_create_requires_permission_by_default():
    assert SkillCreateTool.requires_permission is True


@pytest.mark.asyncio
async def test_skill_create_refuses_duplicate(skills_dir):
    (skills_dir / "a.md").write_text("---\nname: a\ndescription: x\n---\nbody")
    tool = SkillCreateTool()
    ctx = ToolContext(workdir=Path("/tmp"), skills_dir=skills_dir)
    result = await tool.run(SkillCreateInput(name="a", description="x", content="y"), ctx)
    assert result.is_error is True
    assert "already exists" in result.content


@pytest.mark.asyncio
async def test_skill_list_shows_all(skills_dir):
    (skills_dir / "a.md").write_text("---\nname: a\ndescription: Skill A\n---\nx")
    (skills_dir / "b.md").write_text("---\nname: b\ndescription: Skill B\n---\ny")
    tool = SkillListTool()
    ctx = ToolContext(workdir=Path("/tmp"), skills_dir=skills_dir)
    result = await tool.run(SkillListInput(), ctx)
    assert "Skill A" in result.content
    assert "Skill B" in result.content
