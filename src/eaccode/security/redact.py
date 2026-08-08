"""Secret redaction (Phase A.2) — credential-like strings never reach context.

Applied to tool output before it enters the conversation and to stored
sessions. Mirrors the Hermes redact module (smaller scope): API keys,
bearer tokens, and key=value credential pairs.
"""
from __future__ import annotations

import re

_PATTERNS = [
    # OpenAI/Anthropic-style keys: sk-...
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    # GitHub PATs
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    # Google API keys
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    # AWS access key ids
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # generic long tokens (min 24 chars, no spaces)
    re.compile(r"\b[A-Za-z0-9_-]{24,}\b(?=\s|$|['\"])"),
    # Bearer tokens
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    # key=value credential pairs (api_key=, apikey=, password=, token=, secret=)
    re.compile(
        r"(?i)(api[_-]?key|apikey|password|passwd|token|secret|client[_-]?secret)"
        r"\s*[=:]\s*['\"]?[A-Za-z0-9._~+/=-]{6,}['\"]?"
    ),
]


def redact_secrets(text: str) -> str:
    """Mask credential-like strings in *text* with [REDACTED]."""
    if not text:
        return text
    for pattern in _PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def redact_dict(value: dict) -> dict:
    """Recursively redact string values inside a dict (tool arguments)."""
    out = {}
    for k, v in value.items():
        if isinstance(v, str):
            out[k] = redact_secrets(v)
        elif isinstance(v, dict):
            out[k] = redact_dict(v)
        elif isinstance(v, list):
            out[k] = [redact_secrets(i) if isinstance(i, str) else i for i in v]
        else:
            out[k] = v
    return out
