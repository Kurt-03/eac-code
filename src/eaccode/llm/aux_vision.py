"""Auxiliary vision-model client (Phase I.3) — shared by vision_analyze and
video_analyze.

The aux model is a provider marked in providers.yaml with
``extra: {vision: "true"}`` (``eaccode providers add --vision``). When no
such provider exists the tools degrade to a clear setup hint instead of
crashing. Media sources resolve to provider-compatible URLs (http/https,
data: URLs, or local files encoded as data URLs).
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from eaccode.tools.base import ToolResult

# Content-block type per media kind (LiteLLM OpenAI-style message format).
_BLOCK_TYPE = {"image": "image_url", "video": "video_url"}


def resolve_media(source: str, workdir: Path | None) -> str | None:
    """Return a provider-compatible URL (http/https/data:) for a media source.

    Local paths are read and base64-encoded as data URLs (MIME guessed from
    the file name). Returns None when the file cannot be read.
    """
    if source.startswith(("http://", "https://", "data:")):
        return source
    path = Path(source)
    if not path.is_absolute():
        if workdir is None:
            return None
        path = workdir / path
    try:
        data = path.read_bytes()
    except OSError:
        return None
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _vision_provider() -> Any | None:
    """First provider flagged ``extra: {vision: \"true\"}``, else None."""
    from eaccode.config.paths import EaccodePaths
    from eaccode.config.providers import load_providers

    providers = load_providers(EaccodePaths().providers_file)
    return next((p for p in providers if p.extra.get("vision") == "true"), None)


def _no_provider_result() -> ToolResult:
    return ToolResult(
        content=(
            "No vision provider configured. Mark one provider as "
            "vision-capable with `eaccode providers add --vision` "
            "(adds extra: vision=true in providers.yaml)."
        ),
        is_error=True,
    )


def ask_vision(media_url: str, question: str, *, video: bool = False) -> ToolResult:
    """Ask the configured vision provider about an image or video.

    ``video=True`` uses a ``video_url`` content block — the provider model
    must support video input (e.g. Gemini video variants).
    """
    block_type = _BLOCK_TYPE["video" if video else "image"]
    try:
        provider = _vision_provider()
        if provider is None:
            return _no_provider_result()

        from litellm import completion

        resp = completion(
            model=provider.litellm_model(provider.model),
            api_key=provider.api_key.get_secret_value(),
            api_base=provider.base_url,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": block_type, block_type: {"url": media_url}},
                ],
            }],
            max_tokens=1500,
        )
    except Exception as e:
        return ToolResult(
            content=f"Vision request failed: {type(e).__name__}: {e}",
            is_error=True,
        )

    try:
        text = resp.choices[0].message.content or ""
    except Exception:
        text = str(resp)[:2000]
    if not text:
        return ToolResult(
            content="Vision provider returned an empty response.",
            is_error=True,
        )
    return ToolResult(content=text.strip())
