"""Tests for the WebFetch tool (Task 3.6)."""
import httpx
import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.web_fetch import WebFetchInput, WebFetchTool


@pytest.mark.asyncio
async def test_web_fetch_extracts_text(monkeypatch, tmp_path):
    html = "<html><body><h1>Hello</h1><p>World <b>test</b></p></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, request=request)

    # Keep a reference to the real Client BEFORE patching (otherwise the
    # patched name calls itself → infinite recursion)
    orig_client = httpx.Client
    monkeypatch.setattr(
        "eaccode.tools.builtin.web_fetch.httpx.Client",
        lambda *a, **k: orig_client(transport=httpx.MockTransport(handler), *a, **k),
    )
    tool = WebFetchTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(WebFetchInput(url="https://example.com"), ctx)
    assert result.is_error is False
    assert "Hello" in result.content
    assert "World" in result.content
    assert "<b>" not in result.content  # HTML ist entfernt


@pytest.mark.asyncio
async def test_web_fetch_http_error(monkeypatch, tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found", request=request)

    orig_client = httpx.Client
    monkeypatch.setattr(
        "eaccode.tools.builtin.web_fetch.httpx.Client",
        lambda *a, **k: orig_client(transport=httpx.MockTransport(handler), *a, **k),
    )
    tool = WebFetchTool()
    ctx = ToolContext(workdir=tmp_path)
    result = await tool.run(WebFetchInput(url="https://example.com/missing"), ctx)
    assert result.is_error is True
