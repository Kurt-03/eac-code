"""Tests for the agent skill tools (Task 6.5)."""
from pathlib import Path

import pytest

from eaccode.memory.skill_tools import (
    SkillCreateInput,
    SkillCreateTool,
    SkillDeleteInput,
    SkillDeleteTool,
    SkillListInput,
    SkillListTool,
    SkillPatchInput,
    SkillPatchTool,
    SkillRemoveFileInput,
    SkillRemoveFileTool,
    SkillWriteFileInput,
    SkillWriteFileTool,
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


# ---------------------------------------------------------------- A.2


@pytest.mark.asyncio
async def test_create_with_triggers_and_platform(skills_dir):
    tool = SkillCreateTool()
    ctx = ToolContext(workdir=Path("/tmp"), skills_dir=skills_dir)
    result = await tool.run(
        SkillCreateInput(
            name="pytest-skill", description="Run pytest properly",
            content="run with -q", triggers=["pytest"], platform="windows",
        ),
        ctx,
    )
    assert result.is_error is False
    text = (skills_dir / "pytest-skill.md").read_text()
    assert "triggers: [pytest]" in text
    assert "platform: windows" in text


@pytest.mark.asyncio
async def test_delete_removes_skill_and_sidecar(skills_dir):
    p = skills_dir / "gone.md"
    p.write_text("---\nname: gone\ndescription: x\n---\nbody")
    (skills_dir / "gone.usage.json").write_text("{}", encoding="utf-8")
    tool = SkillDeleteTool()
    ctx = ToolContext(workdir=Path("/tmp"), skills_dir=skills_dir)
    result = await tool.run(SkillDeleteInput(name="gone"), ctx)
    assert result.is_error is False
    assert not p.exists()
    assert not (skills_dir / "gone.usage.json").exists()


@pytest.mark.asyncio
async def test_delete_missing_skill_errors(skills_dir):
    tool = SkillDeleteTool()
    ctx = ToolContext(workdir=Path("/tmp"), skills_dir=skills_dir)
    result = await tool.run(SkillDeleteInput(name="nope"), ctx)
    assert result.is_error is True


@pytest.mark.asyncio
async def test_write_and_remove_support_file(skills_dir):
    (skills_dir / "web.md").write_text("---\nname: web\ndescription: x\n---\nbody")
    ctx = ToolContext(workdir=Path("/tmp"), skills_dir=skills_dir)
    w = await SkillWriteFileTool().run(
        SkillWriteFileInput(name="web", path="scripts/fetch.py", content="print(1)"),
        ctx,
    )
    assert w.is_error is False
    assert (skills_dir / "web" / "scripts" / "fetch.py").exists()
    r = await SkillRemoveFileTool().run(
        SkillRemoveFileInput(name="web", path="scripts/fetch.py"), ctx
    )
    assert r.is_error is False
    assert not (skills_dir / "web" / "scripts" / "fetch.py").exists()


@pytest.mark.asyncio
async def test_write_file_requires_existing_skill(skills_dir):
    ctx = ToolContext(workdir=Path("/tmp"), skills_dir=skills_dir)
    result = await SkillWriteFileTool().run(
        SkillWriteFileInput(name="missing", path="x.py", content="x"), ctx
    )
    assert result.is_error is True


def test_extract_user_instruction_variants():
    from eaccode.memory.skill_tools import extract_user_instruction

    assert extract_user_instruction("User instruction: add a test") == "add a test"
    assert extract_user_instruction("Instruction: verify with pytest") == \
        "verify with pytest"
    assert extract_user_instruction("no marker here") is None


@pytest.mark.asyncio
async def test_list_filters_by_provenance(skills_dir):
    (skills_dir / "bundled").mkdir()
    (skills_dir / "a.md").write_text("---\nname: a\ndescription: A\n---\nx")
    (skills_dir / "bundled" / "b.md").write_text(
        "---\nname: b\ndescription: B\n---\ny"
    )
    ctx = ToolContext(workdir=Path("/tmp"), skills_dir=skills_dir)
    result = await SkillListTool().run(SkillListInput(provenance="bundled"), ctx)
    assert "b: B [bundled]" in result.content
    assert "a:" not in result.content
