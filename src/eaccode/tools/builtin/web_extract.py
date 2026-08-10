"""WebExtract tool (Phase I.6) — fetch a URL and extract MAIN content.

Complements web_fetch (which returns raw readable text) with a
readability pass: boilerplate (nav/ads/footers) is stripped so the LLM
gets the article body instead of a menu dump. Uses trafilatura when
available; falls back to the stdlib parser.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


class WebExtractInput(BaseModel):
    url: str = Field(description="URL to fetch and extract")
    max_chars: int = Field(default=30_000, description="Max characters to return")


class WebExtractTool(Tool):
    name = "web_extract"
    tool_class = ToolClass.IDEMPOTENT
    description = (
        "Fetch a URL and extract its MAIN content (boilerplate stripped). "
        "Use for articles and documentation pages; use web_fetch for raw "
        "page text."
    )
    input_model = WebExtractInput
    requires_permission = False

    async def run(self, input: WebExtractInput, ctx: ToolContext) -> ToolResult:
        try:
            with httpx.Client(follow_redirects=True, timeout=30) as client:
                resp = client.get(input.url, headers={"User-Agent": "eaccode/0.1"})
                resp.raise_for_status()
        except Exception as e:
            return ToolResult(content=f"Error extracting {input.url}: {e}", is_error=True)

        text = self._extract(resp.text)
        if not text.strip():
            return ToolResult(
                content=f"No extractable content at {input.url} "
                        f"(status {resp.status_code})",
                is_error=True,
            )
        if len(text) > input.max_chars:
            text = text[: input.max_chars] + "\n[...truncated...]"
        return ToolResult(
            content=f"Extracted from {input.url} (status {resp.status_code}):\n\n{text}",
            metadata={"status": resp.status_code, "bytes": len(text)},
        )

    @staticmethod
    def _extract(html: str) -> str:
        """Main-content extraction: trafilatura first, stdlib fallback."""
        try:
            import trafilatura

            extracted = trafilatura.extract(
                html, include_comments=False, include_tables=True,
                favor_precision=True,
            )
            if extracted:
                return extracted
        except Exception:
            pass
        # Fallback: reuse web_fetch's stdlib text extraction.
        from eaccode.tools.builtin.web_fetch import _TextExtractor

        parser = _TextExtractor()
        parser.feed(html)
        return parser.text()
