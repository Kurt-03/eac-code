"""WebSearch tool (Task 3.6) — key-based providers with graceful degradation.

Provider chain: SERPER_API_KEY (Serper.dev) → BRAVE_API_KEY → clear error.
No key = helpful message telling the user how to enable search.
"""
from __future__ import annotations

import os

import httpx
from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolContext, ToolResult


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    top_n: int = Field(default=8, description="Max results to return")


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web. Returns titles, URLs, and snippets."
    input_model = WebSearchInput
    requires_permission = False

    async def run(self, input: WebSearchInput, ctx: ToolContext) -> ToolResult:
        serper = os.environ.get("SERPER_API_KEY")
        brave = os.environ.get("BRAVE_API_KEY")
        if serper:
            return await self._serper(input, serper)
        if brave:
            return await self._brave(input, brave)
        return ToolResult(
            content="Web search is not configured. Set SERPER_API_KEY "
            "(https://serper.dev) or BRAVE_API_KEY in the environment, "
            "or use web_fetch with a known URL.",
            is_error=True,
        )

    async def _serper(self, input: WebSearchInput, key: str) -> ToolResult:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": key, "Content-Type": "application/json"},
                    json={"q": input.query, "num": input.top_n},
                )
        except Exception as e:
            return ToolResult(content=f"Search error: {e}", is_error=True)
        if resp.status_code != 200:
            return ToolResult(content=f"Search error: HTTP {resp.status_code}", is_error=True)
        results = resp.json().get("organic", [])
        return self._format(results)

    async def _brave(self, input: WebSearchInput, key: str) -> ToolResult:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"X-Subscription-Token": key, "Accept": "application/json"},
                    params={"q": input.query, "count": input.top_n},
                )
        except Exception as e:
            return ToolResult(content=f"Search error: {e}", is_error=True)
        if resp.status_code != 200:
            return ToolResult(content=f"Search error: HTTP {resp.status_code}", is_error=True)
        results = resp.json().get("web", {}).get("results", [])
        return self._format(results)

    @staticmethod
    def _format(results: list[dict]) -> ToolResult:
        if not results:
            return ToolResult(content="No results found.")
        lines = []
        for r in results[:10]:
            title = r.get("title", "")
            link = r.get("link") or r.get("url", "")
            snippet = r.get("snippet", "") or r.get("description", "")
            lines.append(f"{title}\n  {link}\n  {snippet}")
        return ToolResult(content="\n\n".join(lines))
