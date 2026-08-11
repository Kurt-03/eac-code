"""Tests for the WebSearch tool (G.6 — keyless provider registry).

The original Task 3.6 spec (Serper/Brave API keys) was replaced in G.6:
search goes through a pluggable provider registry with a keyless
DuckDuckGo default. Providers can be registered at runtime.
"""
import httpx
import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.web_search import WebSearchInput, WebSearchTool
from eaccode.tools.web_search_registry import (
    SearchResult,
    available_providers,
    register_provider,
    search,
)


def _fake_ddg_handler(request: httpx.Request) -> httpx.Response:
    assert request.url.host == "html.duckduckgo.com"
    return httpx.Response(
        200,
        text=(
            '<a class="result__a" href="https://docs.python.org">'
            "<b>Python</b> Docs</a>"
            '<a class="result__snippet">The official documentation.</a>'
            '<a class="result__a" href="https://pypi.org">PyPI</a>'
        ),
        request=request,
    )


@pytest.fixture
def ddg_mock(monkeypatch):
    monkeypatch.setattr(
        "eaccode.tools.web_search_registry.httpx.get",
        lambda *a, **k: httpx.Response(
            200,
            text=(
                '<a class="result__a" href="https://docs.python.org">'
                "<b>Python</b> Docs</a>"
                '<a class="result__snippet">The official documentation.</a>'
            ),
        ),
    )


def test_available_providers_include_ddg():
    assert "ddg" in available_providers()


def test_search_with_ddg_provider(ddg_mock):
    results = search("python docs", limit=3, provider="ddg")
    assert results
    assert results[0].title == "Python Docs"
    assert results[0].url == "https://docs.python.org"
    assert "official" in results[0].snippet


def test_search_unknown_provider_returns_empty():
    assert search("x", provider="nonexistent") == []


def test_register_custom_provider():
    def fake(query: str, limit: int) -> list[SearchResult]:
        return [SearchResult(title=f"r {query}", url="https://example.com")]

    register_provider("fake-test", fake)
    assert "fake-test" in available_providers()
    results = search("hello", provider="fake-test")
    assert results[0].title == "r hello"


@pytest.mark.asyncio
async def test_tool_returns_results(ddg_mock, tmp_path):
    tool = WebSearchTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(WebSearchInput(query="python documentation"), ctx)
    assert result.is_error is False
    assert "Python Docs" in result.content
    assert "docs.python.org" in result.content


@pytest.mark.asyncio
async def test_tool_unknown_provider_is_error(tmp_path):
    tool = WebSearchTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(
        WebSearchInput(query="anything", provider="serper"), ctx
    )
    assert result.is_error is True
    assert "provider" in result.content.lower()


@pytest.mark.asyncio
async def test_tool_network_failure_returns_empty(monkeypatch, tmp_path):
    def _boom(*a, **k):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr("eaccode.tools.web_search_registry.httpx.get", _boom)
    tool = WebSearchTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(WebSearchInput(query="anything"), ctx)
    assert result.is_error is False  # degrades gracefully
    assert "No results" in result.content
