"""WebFetch tool (Task 3.6) — fetch a URL and extract readable text.

Uses a stdlib HTML parser (no extra deps); returns plain text + links.
"""
from __future__ import annotations

from html.parser import HTMLParser

import httpx
from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolContext, ToolResult


class WebFetchInput(BaseModel):
    url: str = Field(description="URL to fetch")
    max_chars: int = Field(default=20_000, description="Max characters to return")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "tr", "pre"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        import re

        raw = "".join(self._parts)
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in raw.splitlines()]
        return "\n".join(ln for ln in lines if ln)


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch a URL and return its readable text content."
    input_model = WebFetchInput
    requires_permission = False

    async def run(self, input: WebFetchInput, ctx: ToolContext) -> ToolResult:
        try:
            with httpx.Client(follow_redirects=True, timeout=30) as client:
                resp = client.get(input.url, headers={"User-Agent": "eaccode/0.1"})
        except Exception as e:
            return ToolResult(content=f"Error fetching {input.url}: {e}", is_error=True)
        if resp.status_code >= 400:
            return ToolResult(
                content=f"HTTP {resp.status_code} for {input.url}", is_error=True
            )
        parser = _TextExtractor()
        parser.feed(resp.text)
        text = parser.text()
        if len(text) > input.max_chars:
            text = text[: input.max_chars] + "\n[...truncated...]"
        return ToolResult(content=text, metadata={"url": input.url, "chars": len(text)})
