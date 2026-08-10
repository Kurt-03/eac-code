"""Tests for search_files (I.4) and web_extract (I.6) tools."""

import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.search_files import SearchFilesInput, SearchFilesTool
from eaccode.tools.builtin.web_extract import WebExtractInput, WebExtractTool


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path)


class TestSearchFiles:
    @pytest.mark.asyncio
    async def test_finds_matches_in_workdir(self, tmp_path, ctx):
        (tmp_path / "a.py").write_text("def hello():\n    pass\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("x = 1\n", encoding="utf-8")
        tool = SearchFilesTool()
        result = await tool.run(SearchFilesInput(pattern="hello"), ctx)
        assert result.is_error is False
        assert "a.py" in result.content
        assert "hello" in result.content

    @pytest.mark.asyncio
    async def test_no_matches(self, tmp_path, ctx):
        (tmp_path / "a.txt").write_text("nothing here", encoding="utf-8")
        tool = SearchFilesTool()
        result = await tool.run(SearchFilesInput(pattern="zzz_nope"), ctx)
        assert "No matches" in result.content

    @pytest.mark.asyncio
    async def test_glob_filter(self, tmp_path, ctx):
        (tmp_path / "a.py").write_text("marker", encoding="utf-8")
        (tmp_path / "a.md").write_text("marker", encoding="utf-8")
        tool = SearchFilesTool()
        result = await tool.run(
            SearchFilesInput(pattern="marker", file_glob="*.py"), ctx
        )
        assert "a.py" in result.content
        assert "a.md" not in result.content

    @pytest.mark.asyncio
    async def test_limit(self, tmp_path, ctx):
        for i in range(10):
            (tmp_path / f"f{i}.py").write_text("needle\n", encoding="utf-8")
        tool = SearchFilesTool()
        result = await tool.run(SearchFilesInput(pattern="needle", limit=3), ctx)
        assert result.content.count("needle") <= 3 + 2  # matches + header tolerance


class TestWebExtract:
    @pytest.mark.asyncio
    async def test_extracts_main_content(self, monkeypatch, ctx):
        html = ("<html><body><nav>Menu items</nav>"
                "<article><h1>Title</h1><p>The actual content.</p></article>"
                "<footer>Copyright</footer></body></html>")
        monkeypatch.setattr(
            "eaccode.tools.builtin.web_extract.httpx.Client",
            _fake_client(html),
        )
        tool = WebExtractTool()
        result = await tool.run(WebExtractInput(url="https://example.com/x"), ctx)
        assert result.is_error is False
        assert "The actual content" in result.content
        assert result.metadata.get("status") == 200

    @pytest.mark.asyncio
    async def test_http_error(self, monkeypatch, ctx):
        def _raise(*a, **k):
            raise RuntimeError("connection refused")

        monkeypatch.setattr("eaccode.tools.builtin.web_extract.httpx.Client", _raise)
        tool = WebExtractTool()
        result = await tool.run(WebExtractInput(url="https://example.com/x"), ctx)
        assert result.is_error is True
        assert "connection refused" in result.content

    def test_extract_fallback_parser(self):
        tool = WebExtractTool()
        text = tool._extract("<html><body><p>Hello <b>world</b></p></body></html>")
        assert "Hello world" in text.replace("\n", " ")


def _fake_client(html: str):
    class _Resp:
        status_code = 200
        text = html

        def raise_for_status(self):
            return None

    class _Ctx:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, headers=None):
            return _Resp()

    return _Ctx
