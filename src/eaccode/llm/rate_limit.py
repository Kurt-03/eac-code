"""Rate-limit tracking (Phase H.8).

Ported from Hermes' ``agent/rate_limit_tracker.py``. Captures
``x-ratelimit-*`` headers from provider responses and renders them for
``/cost`` (and later ``/usage``). Header schema (12 headers):

    x-ratelimit-limit-requests / -tokens          RPM / TPM caps
    x-ratelimit-limit-requests-1h / -tokens-1h    RPH / TPH caps
    x-ratelimit-remaining-requests / -tokens      remaining in window
    x-ratelimit-remaining-requests-1h / -tokens-1h
    x-ratelimit-reset-requests / -tokens          seconds until reset
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RateLimitBucket:
    limit: int = 0
    remaining: int = 0
    reset_seconds: float = 0.0


@dataclass
class RateLimitState:
    requests: RateLimitBucket = field(default_factory=RateLimitBucket)
    tokens: RateLimitBucket = field(default_factory=RateLimitBucket)
    requests_1h: RateLimitBucket = field(default_factory=RateLimitBucket)
    tokens_1h: RateLimitBucket = field(default_factory=RateLimitBucket)

    @property
    def any_data(self) -> bool:
        return any(
            b.limit or b.remaining or b.reset_seconds
            for b in (self.requests, self.tokens, self.requests_1h, self.tokens_1h)
        )


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_rate_limit_headers(headers) -> RateLimitState:
    """Parse a headers mapping (httpx.Headers or dict) into a state."""
    state = RateLimitState()

    def _get(key: str) -> str | None:
        if headers is None:
            return None
        if isinstance(headers, dict):
            for k, v in headers.items():
                if str(k).lower() == key:
                    return str(v)
            return None
        try:
            return headers.get(key)
        except Exception:
            return None

    state.requests.limit = _safe_int(_get("x-ratelimit-limit-requests"))
    state.requests.remaining = _safe_int(_get("x-ratelimit-remaining-requests"))
    state.requests.reset_seconds = _safe_float(_get("x-ratelimit-reset-requests"))
    state.tokens.limit = _safe_int(_get("x-ratelimit-limit-tokens"))
    state.tokens.remaining = _safe_int(_get("x-ratelimit-remaining-tokens"))
    state.tokens.reset_seconds = _safe_float(_get("x-ratelimit-reset-tokens"))
    state.requests_1h.limit = _safe_int(_get("x-ratelimit-limit-requests-1h"))
    state.requests_1h.remaining = _safe_int(_get("x-ratelimit-remaining-requests-1h"))
    state.tokens_1h.limit = _safe_int(_get("x-ratelimit-limit-tokens-1h"))
    state.tokens_1h.remaining = _safe_int(_get("x-ratelimit-remaining-tokens-1h"))
    return state


def format_rate_limit_compact(state: RateLimitState) -> str:
    """One-line summary for the status bar / /cost."""
    if not state.any_data:
        return ""
    parts = []
    if state.requests.limit:
        parts.append(f"req {state.requests.remaining}/{state.requests.limit}")
    if state.tokens.limit:
        parts.append(f"tok {state.tokens.remaining}/{state.tokens.limit}")
    return " | ".join(parts) if parts else ""
