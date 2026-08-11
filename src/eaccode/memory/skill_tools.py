"""Agent skill tools (Task 6.5) — the agent creates and patches skills itself.

Closes the self-improvement loop: use a skill → find gaps → patch immediately.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from eaccode.memory.skills import discover_skills
from eaccode.memory.skill_usage import record_view
from eaccode.tools.base import Tool, ToolContext, ToolResult


class SkillCreateInput(BaseModel):
    name: str = Field(description="Skill name (lowercase, hyphens)")
    description: str = Field(description="One-line trigger description")
    content: str = Field(description="Full markdown body (steps, commands, pitfalls)")


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
        frontmatter = f"---\nname: {input.name}\ndescription: \"{input.description}\"\n---\n\n"
        path.write_text(frontmatter + input.content, encoding="utf-8")
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
        return ToolResult(content=f"Patched skill {input.name}")


class SkillListInput(BaseModel):
    pass


class SkillListTool(Tool):
    name = "skill_list"
    description = "List all available skills and their descriptions."
    input_model = SkillListInput
    requires_permission = False

    async def run(self, input: SkillListInput, ctx: ToolContext) -> ToolResult:
        skills = discover_skills([ctx.skills_dir])
        if not skills:
            return ToolResult(content="No skills installed yet.")
        # P0.4: listing counts as a view (curator signal).
        for s in skills:
            record_view(s.source)
        lines = [f"- {s.name}: {s.description}" for s in skills]
        return ToolResult(content="\n".join(lines))
