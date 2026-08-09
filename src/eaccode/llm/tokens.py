"""Token estimation and context windows (Task 2.3).

tiktoken (cl100k_base) as an approximation for all models — exact numbers
come from the API usage fields (resp.usage).
"""
from __future__ import annotations

import json

import tiktoken

from eaccode.llm.models import Message

_ENCODING = tiktoken.get_encoding("cl100k_base")

# Rough estimate per image content block
_IMAGE_TOKENS = 1500


def count_message_tokens(messages: list[Message], model: str = "claude-sonnet-4-6") -> int:
    """Approximate token usage of the message list."""
    total = 0
    for m in messages:
        total += 4  # Per-message overhead (role + formatting)
        for block in m.content:
            if block.type == "text":
                total += len(_ENCODING.encode(block.text))
            else:
                total += _IMAGE_TOKENS
        if m.tool_calls:
            for tc in m.tool_calls:
                total += len(_ENCODING.encode(tc.name))
                total += len(_ENCODING.encode(json.dumps(tc.arguments)))
    return total


def model_context_window(model: str) -> int:
    """Known context windows by model family."""
    if "claude" in model:
        return 200_000
    if "gpt-4o" in model or "gpt-4-turbo" in model or "o3" in model or "o4" in model:
        return 128_000
    if "gpt-3.5" in model:
        return 16_000
    if "gemini" in model:
        return 1_000_000
    if "minimax" in model.lower():
        return 200_000  # MiniMax-M3 advertises a 200k window
    if "deepseek" in model.lower():
        return 128_000
    return 128_000  # safe default
