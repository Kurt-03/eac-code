"""Session title generator (D.1) — two-stage: deterministic + LLM upgrade.

Stage 1 derives a title instantly from the first user message (no LLM
call). Stage 2 optionally upgrades it asynchronously with the LLM.
Provenance tracks who set the title: ``derived < llm < user`` — a
user-given title always wins; an LLM title only replaces a derived one.
"""

from __future__ import annotations

from typing import Any

PROVENANCE_ORDER = {"derived": 0, "llm": 1, "user": 2}
DEFAULT_PROVENANCE = "derived"


def should_upgrade(current: str, new: str) -> bool:
    """True when *new* provenance may replace *current*."""
    return PROVENANCE_ORDER.get(new, 0) > PROVENANCE_ORDER.get(current, 0)


def derive_title(first_user_text: str, max_len: int = 40) -> str:
    """Deterministic stage-1 title from the first user message."""
    text = " ".join(first_user_text.split())
    if not text:
        return "untitled"
    title = text[:max_len]
    if len(text) > max_len:
        title = title.rstrip() + "…"
    return title


def _title_llm_prompt(text: str) -> str:
    return (
        "Create a short session title (max 6 words, no quotes) for a "
        f"coding-agent conversation starting with: {text[:200]!r}\n"
        "Reply with the title only."
    )


async def llm_title_async(
    text: str,
    provider: Any | None = None,
    timeout: float = 15.0,
) -> str | None:
    """Stage-2 LLM upgrade; None when unavailable or the call fails.

    Uses the given provider (or the default one). Failures never raise —
    the deterministic title stays.
    """
    try:
        if provider is None:
            from eaccode.config.paths import EaccodePaths
            from eaccode.config.providers import load_providers

            providers = load_providers(EaccodePaths().providers_file)
            if not providers:
                return None
            provider = providers[0]
        from litellm import acompletion

        resp = await acompletion(
            model=provider.model,
            messages=[{"role": "user", "content": _title_llm_prompt(text)}],
            api_key=provider.api_key.get_secret_value() if provider.api_key else None,
            base_url=provider.base_url or None,
            timeout=timeout,
            temperature=0,
            max_tokens=20,
        )
        title = (resp.choices[0].message.content or "").strip().strip("\"'")
        return title[:60] if title else None
    except Exception:
        return None
