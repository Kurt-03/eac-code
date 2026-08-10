"""Tests for vision_analyze (Phase I.3)."""

import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.builtin.vision import VisionAnalyzeInput, VisionAnalyzeTool


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path)


class TestVision:
    def test_url_passthrough(self):
        assert VisionAnalyzeTool._resolve_image(
            "https://example.com/x.png", None
        ) == "https://example.com/x.png"

    def test_data_url_passthrough(self):
        assert VisionAnalyzeTool._resolve_image("data:image/png;base64,AAA", None) \
            == "data:image/png;base64,AAA"

    def test_local_file_becomes_data_url(self, tmp_path):
        img = tmp_path / "pic.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        out = VisionAnalyzeTool._resolve_image("pic.png", tmp_path)
        assert out.startswith("data:image/png;base64,")

    def test_missing_file_returns_none(self, tmp_path):
        assert VisionAnalyzeTool._resolve_image("nope.png", tmp_path) is None

    def test_relative_path_resolves_against_workdir(self, tmp_path):
        img = tmp_path / "sub" / "x.jpg"
        img.parent.mkdir()
        img.write_bytes(b"jpegdata")
        out = VisionAnalyzeTool._resolve_image("sub/x.jpg", tmp_path)
        assert out.startswith("data:image/jpeg;base64,")

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


class _FakePathsNoVision:
    providers_file = "C:/nonexistent/providers.yaml"
