"""tool_search (H.17) — discover tools by keyword.

With a large registry the model may not remember every tool name; this
tool lets it search by keyword and get name + description + input keys
for the matches (used by the agent, not by the permission system).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult

# H.17: set by the factory once the registry exists (avoids a circular
# import — the registry is built from the tool list).
_registry_lookup = None


def set_registry_lookup(fn) -> None:
    global _registry_lookup
    _registry_lookup = fn


class ToolSearchInput(BaseModel):
    query: str = Field(description="Keyword to search tool names/descriptions")
    limit: int = Field(default=5, ge=1, le=20, description="Max matches")


class ToolSearchTool(Tool):
    name = "tool_search"
    description = (
        "Search the available tool registry by keyword. Returns the "
        "matching tool names, their purpose, and input parameter keys. "
        "Use when you are unsure which tool fits a task."
    )
    input_model = ToolSearchInput
    requires_permission = False
    tool_class = ToolClass.IDEMPOTENT

    async def run(self, input: ToolSearchInput, ctx: ToolContext) -> ToolResult:
        registry = _registry_lookup() if _registry_lookup else None
        if registry is None:
            return ToolResult(
                content="tool registry not available in this context.",
                is_error=True,
            )
        query = input.query.lower()
        matches = []
        for tool in registry.list():
            haystack = f"{tool.name} {tool.description}".lower()
            if query in haystack:
                keys = list(getattr(tool.input_model, "model_fields", {}).keys())
                matches.append(
                    (tool.name, tool.description[:120], ", ".join(keys[:8]))
                )
            if len(matches) >= input.limit:
                break
        if not matches:
            return ToolResult(
                content=f"No tools match {input.query!r}.", is_error=False
            )
        lines = [f"Tools matching {input.query!r}:"]
        for name, desc, keys in matches:
            lines.append(f"  {name}: {desc}")
            if keys:
                lines.append(f"      args: {keys}")
        return ToolResult(content="\n".join(lines))
