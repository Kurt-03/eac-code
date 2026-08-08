"""API error classification (Phase A.4) — decide retry vs fallback vs stop.

Mirrors Hermes' error_classifier at small scope: a 402 (budget) or 400
(schema) will never succeed on retry; a 401/403 means credentials are
wrong (fallback, don't retry); 429/5xx/timeouts are transient (retry).
"""
from __future__ import annotations

import enum
import re


class FailoverReason(enum.Enum):
    AUTH = "auth"            # credentials wrong → try fallback, no retry
    BUDGET = "budget"        # 402 → stop, tell the user
    SCHEMA = "schema"        # 400 → stop (retry won't fix it)
    OVERLOAD = "overload"    # 429 → retry with backoff
    SERVER = "server"        # 5xx → retry with backoff
    TIMEOUT = "timeout"      # network timeout → retry
    UNKNOWN = "unknown"      # default → retry


@enum.unique
class RetryPolicy(enum.Enum):
    RETRY = "retry"          # transient — retry, then fallback
    FALLBACK = "fallback"    # auth — skip retry, go straight to fallback
    STOP = "stop"            # permanent — raise immediately


class ClassifiedError(Exception):
    """An API error with its classification attached."""

    def __init__(self, reason: FailoverReason, policy: RetryPolicy, message: str):
        super().__init__(message)
        self.reason = reason
        self.policy = policy


_STATUS_CODE_RE = re.compile(r"status_code[= ](\d{3})|\bHTTP (\d{3})\b|(\d{3}) (Unauthorized|Forbidden|Payment|Not Found|Bad Request)")


def _extract_status_code(error: Exception) -> int | None:
    text = f"{type(error).__name__}: {error}"
    m = _STATUS_CODE_RE.search(text)
    if m:
        for group in m.groups():
            if group and group.isdigit():
                return int(group)
    # httpx-style: 'Client error '401 Unauthorized' for url ...'
    m = re.search(r"\b(\d{3})\b", text)
    if m:
        return int(m.group(1))
    return None


def classify_api_error(error: Exception) -> ClassifiedError:
    """Classify any exception raised by the LLM client."""
    name = type(error).__name__.lower()
    status = _extract_status_code(error)

    if "timeout" in name or "timedout" in name or isinstance(error, TimeoutError):
        return ClassifiedError(FailoverReason.TIMEOUT, RetryPolicy.RETRY, str(error))
    if status == 401 or status == 403 or "unauthorized" in name or "authentication" in name:
        return ClassifiedError(FailoverReason.AUTH, RetryPolicy.FALLBACK, str(error))
    if status == 402 or "insufficient" in str(error).lower() or "payment" in str(error).lower():
        return ClassifiedError(FailoverReason.BUDGET, RetryPolicy.STOP, str(error))
    if status == 400 or status == 404 or status == 422:
        return ClassifiedError(FailoverReason.SCHEMA, RetryPolicy.STOP, str(error))
    if status == 429 or "rate limit" in str(error).lower() or "ratelimit" in name:
        return ClassifiedError(FailoverReason.OVERLOAD, RetryPolicy.RETRY, str(error))
    if status and status >= 500:
        return ClassifiedError(FailoverReason.SERVER, RetryPolicy.RETRY, str(error))
    return ClassifiedError(FailoverReason.UNKNOWN, RetryPolicy.RETRY, str(error))
