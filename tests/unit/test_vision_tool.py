"""Tests for vision_analyze + video_analyze (Phase I.3)."""

from pathlib import Path

import pytest

from eaccode.llm.aux_vision import resolve_media
from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.vision import (
    VideoAnalyzeInput,
    VideoAnalyzeTool,
    VisionAnalyzeInput,
    VisionAnalyzeTool,
)


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path)


class TestResolveMedia:
    def test_url_passthrough(self):
        assert resolve_media("https://example.com/x.png", None) \
            == "https://example.com/x.png"

    def test_data_url_passthrough(self):
        assert resolve_media("data:image/png;base64,AAA", None) \
            == "data:image/png;base64,AAA"

    def test_local_file_becomes_data_url(self, tmp_path):
        img = tmp_path / "pic.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        out = resolve_media("pic.png", tmp_path)
        assert out.startswith("data:image/png;base64,")

    def test_missing_file_returns_none(self, tmp_path):
        assert resolve_media("nope.png", tmp_path) is None

    def test_relative_path_resolves_against_workdir(self, tmp_path):
        img = tmp_path / "sub" / "x.jpg"
        img.parent.mkdir()
        img.write_bytes(b"jpegdata")
        out = resolve_media("sub/x.jpg", tmp_path)
        assert out.startswith("data:image/jpeg;base64,")

    def test_video_file_becomes_video_data_url(self, tmp_path):
        vid = tmp_path / "clip.mp4"
        vid.write_bytes(b"fakevideo")
        out = resolve_media("clip.mp4", tmp_path)
        assert out.startswith("data:video/mp4;base64,")

    def test_no_workdir_and_relative_path_returns_none(self):
        assert resolve_media("x.png", None) is None


class _FakeProvider:
    def __init__(self) -> None:
        from pydantic import SecretStr

        self.model = "vision-model"
        self.base_url = None
        self.extra = {"vision": "true"}
        self._key = SecretStr("sk-test")

    def litellm_model(self, model: str) -> str:
        return f"provider/{model}"

    @property
    def api_key(self):
        return self._key


class TestVision:
    @pytest.mark.asyncio
    async def test_no_vision_provider_graceful(self, ctx, monkeypatch):
        """Without a vision-marked provider the tool must degrade cleanly."""
        monkeypatch.setattr(
            "eaccode.config.paths.EaccodePaths", _FakePathsNoVision
        )
        tool = VisionAnalyzeTool()
        result = await tool.run(
            VisionAnalyzeInput(image="https://example.com/x.png"), ctx
        )
        assert result.is_error is True
        assert "vision" in result.content.lower()

    @pytest.mark.asyncio
    async def test_missing_image_file(self, ctx):
        tool = VisionAnalyzeTool()
        result = await tool.run(VisionAnalyzeInput(image="ghost.png"), ctx)
        assert result.is_error is True
        assert "Cannot read image" in result.content

    @pytest.mark.asyncio
    async def test_happy_path_sends_image_block(self, ctx, monkeypatch):
        captured = {}

        def fake_completion(**kwargs):
            captured.update(kwargs)
            return _FakeResponse("a red apple on a table")

        monkeypatch.setattr("eaccode.llm.aux_vision._vision_provider",
                            lambda: _FakeProvider())
        monkeypatch.setattr("litellm.completion", fake_completion)
        tool = VisionAnalyzeTool()
        result = await tool.run(
            VisionAnalyzeInput(image="https://example.com/x.png",
                               question="What is this?"),
            ctx,
        )
        assert result.is_error is False
        assert result.content == "a red apple on a table"
        block = captured["messages"][0]["content"][1]
        assert block["type"] == "image_url"
        assert block["image_url"]["url"] == "https://example.com/x.png"


class TestVideo:
    @pytest.mark.asyncio
    async def test_missing_video_file(self, ctx):
        tool = VideoAnalyzeTool()
        result = await tool.run(VideoAnalyzeInput(video="ghost.mp4"), ctx)
        assert result.is_error is True
        assert "Cannot read video" in result.content

    @pytest.mark.asyncio
    async def test_no_vision_provider_graceful(self, ctx, monkeypatch):
        monkeypatch.setattr(
            "eaccode.config.paths.EaccodePaths", _FakePathsNoVision
        )
        tool = VideoAnalyzeTool()
        result = await tool.run(
            VideoAnalyzeInput(video="https://example.com/clip.mp4"), ctx
        )
        assert result.is_error is True
        assert "vision" in result.content.lower()

    @pytest.mark.asyncio
    async def test_happy_path_sends_video_block(self, ctx, monkeypatch):
        captured = {}

        def fake_completion(**kwargs):
            captured.update(kwargs)
            return _FakeResponse("a dog running in a park")

        monkeypatch.setattr("eaccode.llm.aux_vision._vision_provider",
                            lambda: _FakeProvider())
        monkeypatch.setattr("litellm.completion", fake_completion)
        tool = VideoAnalyzeTool()
        result = await tool.run(
            VideoAnalyzeInput(video="https://example.com/clip.mp4",
                              question="What happens?"),
            ctx,
        )
        assert result.is_error is False
        assert result.content == "a dog running in a park"
        block = captured["messages"][0]["content"][1]
        assert block["type"] == "video_url"
        assert block["video_url"]["url"] == "https://example.com/clip.mp4"

    @pytest.mark.asyncio
    async def test_provider_error_is_reported(self, ctx, monkeypatch):
        def boom(**kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr("eaccode.llm.aux_vision._vision_provider",
                            lambda: _FakeProvider())
        monkeypatch.setattr("litellm.completion", boom)
        tool = VideoAnalyzeTool()
        result = await tool.run(
            VideoAnalyzeInput(video="https://example.com/clip.mp4"), ctx
        )
        assert result.is_error is True
        assert "RuntimeError" in result.content


class _FakeResponse:
    def __init__(self, text: str):
        self._text = text

    @property
    def choices(self):
        return [_FakeChoice(self._text)]


class _FakeChoice:
    def __init__(self, text: str):
        self.message = _FakeMessage(text)


class _FakeMessage:
    def __init__(self, text: str):
        self.content = text


class _FakePathsNoVision:
    providers_file = Path("C:/nonexistent/providers.yaml")
