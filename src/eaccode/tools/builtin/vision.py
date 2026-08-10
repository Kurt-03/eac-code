"""vision_analyze + video_analyze tools (Phase I.3) — media description via a
vision-capable provider (BYOK, LiteLLM). Graceful degradation when no vision
model is configured: clear setup hint instead of a crash.

Both tools share the aux-model path in ``eaccode.llm.aux_vision``; the
provider must support image_url/video_url content blocks (e.g. MiniMax-M3
vision variants, OpenAI gpt-4o, Gemini). video_analyze needs a
video-capable model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from eaccode.llm.aux_vision import ask_vision, resolve_media
from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


class VisionAnalyzeInput(BaseModel):
    image: str = Field(description="Image URL (http/https), local file path, or data URL")
    question: str = Field(
        default="Describe this image in detail.",
        description="Specific question about the image",
    )


class VideoAnalyzeInput(BaseModel):
    video: str = Field(description="Video URL (http/https), local file path, or data URL")
    question: str = Field(
        default="Describe this video in detail, noting key scenes and events.",
        description="Specific question about the video",
    )


class VisionAnalyzeTool(Tool):
    name = "vision_analyze"
    tool_class = ToolClass.IDEMPOTENT
    description = (
        "Load an image (URL, local file path, or data URL) and answer a "
        "question about it using a vision-capable model. Requires a vision "
        "provider in the eaccode configuration."
    )
    input_model = VisionAnalyzeInput
    requires_permission = False

    async def run(self, input: VisionAnalyzeInput, ctx: ToolContext) -> ToolResult:
        media_url = resolve_media(input.image, ctx.workdir)
        if media_url is None:
            return ToolResult(
                content=f"Cannot read image: {input.image}",
                is_error=True,
            )
        return ask_vision(media_url, input.question)


class VideoAnalyzeTool(Tool):
    name = "video_analyze"
    tool_class = ToolClass.IDEMPOTENT
    description = (
        "Load a video (URL, local file path, or data URL) and answer a "
        "question about it using a video-capable model. Requires a vision "
        "provider whose model supports video input."
    )
    input_model = VideoAnalyzeInput
    requires_permission = False

    async def run(self, input: VideoAnalyzeInput, ctx: ToolContext) -> ToolResult:
        media_url = resolve_media(input.video, ctx.workdir)
        if media_url is None:
            return ToolResult(
                content=f"Cannot read video: {input.video}",
                is_error=True,
            )
        return ask_vision(media_url, input.question, video=True)
