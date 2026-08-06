"""Tests for the WebSearch tool (Task 3.6)."""
import httpx
import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.web_search import WebSearchInput, WebSearchTool


@pytest.mark.asyncio
async def test_web_search_serper(monkeypatch, tmp_path):
    """Serper (key-based) returns structured results."""
    monkeypatch.setenv("SERPER_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "google.serper.dev"
        return httpx.Response(
            200,
            json={
                "organic": [
                    {"title": "Python Docs", "link": "https://docs.python.org",
                     "snippet": "The official Python documentation."}
                ]
            },
            request=request,
        )

    orig = httpx.Client
    monkeypatch.setattr(
        "eaccode.tools.builtin.web_search.httpx.Client",
        lambda *a, **k: orig(*a, transport=httpx.MockTransport(handler), **k),
    )
    tool = WebSearchTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(WebSearchInput(query="python documentation"), ctx)
    assert result.is_error is False
    assert "Python Docs" in result.content
    assert "docs.python.org" in result.content


@pytest.mark.asyncio
async def test_web_search_no_key_degrades_gracefully(tmp_path, monkeypatch):
    """Ohne konfigurierten Key: klare Meldung statt Crash."""
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    tool = WebSearchTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(WebSearchInput(query="anything"), ctx)
    assert result.is_error is True
    assert "key" in result.content.lower()
