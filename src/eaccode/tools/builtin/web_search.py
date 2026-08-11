"""web_search tool (G.6) — keyless search via the provider registry."""

from __future__ import annotations

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult
from eaccode.tools.web_search_registry import available_providers, search


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    limit: int = Field(default=5, ge=1, le=10, description="Max results")
    provider: str = Field(default="ddg", description="Search provider name")


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the web (keyless DuckDuckGo by default). Returns "
        "title/url/snippet rows. Use when the answer needs current "
        "public information."
    )
    input_model = WebSearchInput
    requires_permission = False
    tool_class = ToolClass.RUNAWAY  # network calls can be slow

    async def run(self, input: WebSearchInput, ctx: ToolContext) -> ToolResult:
        if input.provider not in available_providers():
            return ToolResult(
                content=f"Unknown provider {input.provider!r}. "
                        f"Available: {', '.join(available_providers())}",
                is_error=True,
            )
        results = search(input.query, input.limit, input.provider)
        if not results:
            return ToolResult(
                content=f"No results for {input.query!r} (provider "
                        f"{input.provider}).",
                is_error=False,
            )
        lines = [f"Search results for {input.query!r} "
                 f"({len(results)} via {input.provider}):"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.title}")
            lines.append(f"   {r.url}")
            if r.snippet:
                lines.append(f"   {r.snippet[:200]}")
        return ToolResult(content="\n".join(lines))
