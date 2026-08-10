"""vision_analyze tool (Phase I.3) — image description via a vision-capable
provider (BYOK, LiteLLM). Graceful degradation when no vision model is
configured: clear setup hint instead of a crash.

Uses the same providers.yaml machinery as the main LLM client; the
provider must support image_url content blocks (e.g. MiniMax-M3 vision
variants, OpenAI gpt-4o, etc.).
"""

from __future__ import annotations

import base64
from pathlib import Path

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


class VisionAnalyzeInput(BaseModel):
    image: str = Field(description="Image URL (http/https), local file path, or data URL")
    question: str = Field(
        default="Describe this image in detail.",
        description="Specific question about the image",
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
        image_url = self._resolve_image(input.image, ctx.workdir)
        if image_url is None:
            return ToolResult(
                content=f"Cannot read image: {input.image}",
                is_error=True,
            )
        try:
            return await self._ask(image_url, input.question)
        except Exception as e:
            return ToolResult(
                content=f"Vision request failed: {type(e).__name__}: {e}",
                is_error=True,
            )

    @staticmethod
    def _resolve_image(image: str, workdir: Path) -> str | None:
        """Return an image_url-compatible string (URL or data URL)."""
        if image.startswith(("http://", "https://", "data:")):
            return image
        path = Path(image)
        if not path.is_absolute():
            path = workdir / path
        try:
            data = path.read_bytes()
        except OSError:
            return None
        import mimetypes

        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"

    async def _ask(self, image_url: str, question: str) -> ToolResult:
        """Call the configured vision provider via LiteLLM.

        Vision providers are marked in providers.yaml with
        ``extra: {vision: "true"}`` (eaccode providers add --vision).
        """
        from eaccode.config.paths import EaccodePaths
        from eaccode.config.providers import load_providers

        providers = load_providers(EaccodePaths().providers_file)
        vision = next(
            (p for p in providers if p.extra.get("vision") == "true"), None
        )
        if vision is None:
            return ToolResult(
                content=(
                    "No vision provider configured. Mark one provider as "
                    "vision-capable with `eaccode providers add --vision` "
                    "(adds extra: vision=true in providers.yaml)."
                ),
                is_error=True,
            )
        from litellm import completion

        resp = completion(
            model=vision.litellm_model(vision.model),
            api_key=vision.api_key.get_secret_value(),
            api_base=vision.base_url,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }],
            max_tokens=1500,
        )
        try:
            text = resp.choices[0].message.content or ""
        except Exception:
            text = str(resp)[:2000]
        if not text:
            return ToolResult(content="Vision provider returned an empty response.", is_error=True)
        return ToolResult(content=text.strip())
