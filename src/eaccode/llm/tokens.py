"""Token-Schätzung und Kontext-Fenster (Task 2.3).

tiktoken (cl100k_base) als Näherung für alle Modelle — exakte Zahlen
kommen aus den API-Usage-Feldern (resp.usage).
"""
from __future__ import annotations

import json

import tiktoken

from eaccode.llm.models import Message

_ENCODING = tiktoken.get_encoding("cl100k_base")

# Grobe Schätzung pro Bild-Content-Block
_IMAGE_TOKENS = 1500


def count_message_tokens(messages: list[Message], model: str = "claude-sonnet-4-6") -> int:
    """Näherungsweiser Token-Verbrauch der Nachrichtenliste."""
    total = 0
    for m in messages:
        total += 4  # Overhead pro Nachricht (Rolle + Formatierung)
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
    """Bekannte Kontext-Fenster nach Modell-Familie."""
    if "claude" in model:
        return 200_000
    if "gpt-4o" in model or "gpt-4-turbo" in model or "o3" in model or "o4" in model:
        return 128_000
    if "gpt-3.5" in model:
        return 16_000
    if "gemini" in model:
        return 1_000_000
    return 128_000  # safe default
