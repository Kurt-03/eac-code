"""Retry utilities — jittered backoff + Retry-After respect (Phase H.7).

Ported from Hermes' ``agent/retry_utils.py``. Fixed exponential backoff
causes thundering-herd retry spikes when multiple sessions hit the same
rate-limited provider concurrently; jittered delays decorrelate them.
The ``Retry-After`` header is respected when present.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime


def parse_retry_after_seconds(value_or_headers: object) -> float | None:
    """Parse a Retry-After header value (seconds or HTTP-date) or a
    headers mapping containing it. Returns None when absent/unparseable.

    Mirrors Hermes: accepts the raw header string OR a dict-like headers
    object (httpx.Headers / dict).
    """
    value = None
    if isinstance(value_or_headers, str):
        value = value_or_headers
    elif isinstance(value_or_headers, dict):
        for key, v in value_or_headers.items():
            if str(key).lower() == "retry-after":
                value = v
                break
    elif hasattr(value_or_headers, "get"):
        value = value_or_headers.get("Retry-After") or value_or_headers.get("retry-after")
    if value is None:
        return None

    try:
        seconds = float(value)
        return max(0.0, seconds)
    except (TypeError, ValueError):
        pass

    # HTTP-date format (rare in practice): parse and diff.
    try:
        from email.utils import parsedate_to_datetime

        retry_at = parsedate_to_datetime(value)
        delta = (retry_at - datetime.now(UTC)).total_seconds()
        return max(0.0, delta)
    except Exception:
        return None


def jittered_backoff(attempt: int, *, base: float = 1.0, cap: float = 60.0,
                     jitter: float = 0.3) -> float:
    """Decorrelated jittered backoff delay in seconds.

    ``exp = min(cap, base * 2**attempt)`` then +/- up to *jitter* of the
    result, re-capped so the delay never exceeds *cap*. attempt is 0-based.
    """
    exp = min(cap, base * (2 ** attempt))
    spread = exp * jitter
    delay = exp - spread + random.random() * (2 * spread)
    return max(0.0, min(cap, delay))


def adaptive_rate_limit_backoff(error: object, attempt: int, *, base: float = 1.0,
                                cap: float = 120.0) -> float:
    """Backoff for a rate-limit error: prefer Retry-After, else jittered."""
    retry_after = None
    response = getattr(error, "response", None)
    if response is not None:
        # httpx.Response has .headers; plain objects may carry .headers too.
        headers = getattr(response, "headers", None) or response
        retry_after = parse_retry_after_seconds(headers)
    if retry_after is not None:
        return min(retry_after, cap)
    return jittered_backoff(attempt, base=base, cap=cap)
