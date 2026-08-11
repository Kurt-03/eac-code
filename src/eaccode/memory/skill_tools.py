"""Agent skill tools (Task 6.5 / A.2) — the agent manages skills itself.

Closes the self-improvement loop: use a skill → find gaps → patch
immediately. A.2 extends the manager to 5+ actions:
create / patch / delete / write_file / remove_file, plus
``extract_user_instruction`` and a provenance filter on listings.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from eaccode.memory.skill_usage import record_view, record_write
from eaccode.memory.skills import discover_skills
from eaccode.tools.base import Tool, ToolContext, ToolResult


def extract_user_instruction(text: str) -> str | None:
    """Pull an explicit user instruction out of a message/result.

    Recognizes ``User instruction: ...`` (Hermes-style marker) and
    ``Instruction: ...``; returns None when absent.
    """
    for pattern in (
        r"(?:^|\n)\s*(?:User\s+)?instruction:\s*(.+?)(?:\n\s*\n|\Z)",
        r"(?:^|\n)\s*(?:User\s+)?instruction:\s*(.+)",
    ):
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def _frontmatter(name: str, description: str, triggers: list[str],
                 platform: str | None) -> str:
    lines = [f"name: {name}", f"description: \"{description}\""]
    if triggers:
        lines.append("triggers: [" + ", ".join(triggers) + "]")
    if platform:
        lines.append(f"platform: {platform}")
    return "---\n" + "\n".join(lines) + "\n---\n\n"


class SkillCreateInput(BaseModel):
    name: str = Field(description="Skill name (lowercase, hyphens)")
    description: str = Field(description="One-line trigger description")
    content: str = Field(description="Full markdown body (steps, commands, pitfalls)")
    triggers: list[str] = Field(
        default_factory=list,
        description="Optional keywords that auto-load this skill",
    )
    platform: str | None = Field(
        default=None,
        description="Optional OS restriction: windows | linux | darwin",
    )


class SkillCreateTool(Tool):
    name = "skill_create"
    description = (
        "Create a new reusable skill. Use after solving a difficult task "
        "(5+ tool calls) so the approach is reusable."
    )
    input_model = SkillCreateInput
    requires_permission = True  # writing into the skills directory

    async def run(self, input: SkillCreateInput, ctx: ToolContext) -> ToolResult:
        skills_dir = ctx.skills_dir
        skills_dir.mkdir(parents=True, exist_ok=True)
        path = skills_dir / f"{input.name}.md"
        if path.exists():
            return ToolResult(
                content=f"Skill '{input.name}' already exists. Use skill_patch to update it.",
                is_error=True,
            )
        frontmatter = _frontmatter(input.name, input.description,
                                   input.triggers, input.platform)
        path.write_text(frontmatter + input.content, encoding="utf-8")
        record_write(path)
        return ToolResult(content=f"Created skill {input.name} at {path}")


class SkillPatchInput(BaseModel):
    name: str = Field(description="Skill name to patch")
    old_string: str = Field(description="Exact text to find (must be unique)")
    new_string: str = Field(description="Replacement text")


class SkillPatchTool(Tool):
    name = "skill_patch"
    description = (
        "Update an existing skill. Use immediately when you discover the skill "
        "is outdated or missing steps."
    )
    input_model = SkillPatchInput
    requires_permission = True

    async def run(self, input: SkillPatchInput, ctx: ToolContext) -> ToolResult:
        path = ctx.skills_dir / f"{input.name}.md"
        if not path.exists():
            return ToolResult(
                content=f"Skill '{input.name}' not found. Use skill_create first.",
                is_error=True,
            )
        text = path.read_text(encoding="utf-8")
        n = text.count(input.old_string)
        if n == 0:
            return ToolResult(
                content="old_string not found in skill. Read it first.", is_error=True
            )
        if n > 1:
            return ToolResult(
                content="old_string matches multiple times. Be more specific.",
                is_error=True,
            )
        path.write_text(text.replace(input.old_string, input.new_string, 1), encoding="utf-8")
        record_write(path)
        return ToolResult(content=f"Patched skill {input.name}")


class SkillDeleteInput(BaseModel):
    name: str = Field(description="Skill name to delete")


class SkillDeleteTool(Tool):
    name = "skill_delete"
    description = "Delete a skill file (and its usage sidecar)."
    input_model = SkillDeleteInput
    requires_permission = True

    async def run(self, input: SkillDeleteInput, ctx: ToolContext) -> ToolResult:
        path = ctx.skills_dir / f"{input.name}.md"
        if not path.exists():
            return ToolResult(
                content=f"Skill '{input.name}' not found.", is_error=True
            )
        path.unlink()
        sidecar = path.with_name(path.stem + ".usage.json")
        if sidecar.exists():
            sidecar.unlink()
        return ToolResult(content=f"Deleted skill {input.name}")


class SkillWriteFileInput(BaseModel):
    name: str = Field(description="Skill name")
    path: str = Field(
        description="Relative path inside the skill directory "
                    "(e.g. scripts/verify.py, references/api.md)"
    )
    content: str = Field(description="Full file content")


class SkillWriteFileTool(Tool):
    name = "skill_write_file"
    description = (
        "Write a supporting file inside a skill directory "
        "(scripts/, references/, templates/). The skill must exist."
    )
    input_model = SkillWriteFileInput
    requires_permission = True

    async def run(self, input: SkillWriteFileInput, ctx: ToolContext) -> ToolResult:
        skill_dir = ctx.skills_dir / input.name
        skill_file = skill_dir.with_suffix(".md")
        if not skill_file.exists() and not (skill_dir / "SKILL.md").exists():
            return ToolResult(
                content=f"Skill '{input.name}' not found. Use skill_create first.",
                is_error=True,
            )
        target = skill_dir / input.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(input.content, encoding="utf-8")
        return ToolResult(content=f"Wrote {target}")


class SkillRemoveFileInput(BaseModel):
    name: str = Field(description="Skill name")
    path: str = Field(description="Relative path inside the skill directory")


class SkillRemoveFileTool(Tool):
    name = "skill_remove_file"
    description = "Remove a supporting file from a skill directory."
    input_model = SkillRemoveFileInput
    requires_permission = True

    async def run(self, input: SkillRemoveFileInput, ctx: ToolContext) -> ToolResult:
        target = ctx.skills_dir / input.name / input.path
        if not target.exists():
            return ToolResult(
                content=f"File not found: {target}", is_error=True
            )
        target.unlink()
        return ToolResult(content=f"Removed {target}")


class SkillListInput(BaseModel):
    provenance: str | None = Field(
        default=None,
        description="Filter: bundled | user | curator | pinned",
    )


class SkillListTool(Tool):
    name = "skill_list"
    description = "List all available skills and their descriptions."
    input_model = SkillListInput
    requires_permission = False

    async def run(self, input: SkillListInput, ctx: ToolContext) -> ToolResult:
        skills = discover_skills([ctx.skills_dir])
        if input.provenance:
            skills = [s for s in skills if s.provenance == input.provenance]
        if not skills:
            return ToolResult(content="No skills installed yet.")
        # P0.4: listing counts as a view (curator signal).
        for s in skills:
            record_view(s.source)
        lines = [f"- {s.name}: {s.description} [{s.provenance}]" for s in skills]
        return ToolResult(content="\n".join(lines))
