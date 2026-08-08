"""Tests for API error classification (Phase A.4)."""
import pytest

from eaccode.llm.errors import (
    FailoverReason,
    RetryPolicy,
    classify_api_error,
)


class FakeStatusError(Exception):
    def __init__(self, status: int):
        super().__init__(f"Client error '{status}' for url 'https://x'")
        self.status_code = status


def test_401_is_auth_fallback():
    e = classify_api_error(FakeStatusError(401))
    assert e.reason == FailoverReason.AUTH
    assert e.policy == RetryPolicy.FALLBACK


def test_402_is_budget_stop():
    e = classify_api_error(FakeStatusError(402))
    assert e.reason == FailoverReason.BUDGET
    assert e.policy == RetryPolicy.STOP


def test_400_is_schema_stop():
    e = classify_api_error(FakeStatusError(400))
    assert e.reason == FailoverReason.SCHEMA
    assert e.policy == RetryPolicy.STOP


def test_429_is_overload_retry():
    e = classify_api_error(FakeStatusError(429))
    assert e.reason == FailoverReason.OVERLOAD
    assert e.policy == RetryPolicy.RETRY


def test_500_is_server_retry():
    e = classify_api_error(FakeStatusError(503))
    assert e.reason == FailoverReason.SERVER
    assert e.policy == RetryPolicy.RETRY


def test_timeout_is_retry():
    e = classify_api_error(TimeoutError("took too long"))
    assert e.reason == FailoverReason.TIMEOUT
    assert e.policy == RetryPolicy.RETRY


def test_ratelimit_name_detected():
    class RateLimitError(Exception):
        pass

    e = classify_api_error(RateLimitError("rate limit reached"))
    assert e.reason == FailoverReason.OVERLOAD


def test_unknown_defaults_to_retry():
    e = classify_api_error(ValueError("weird"))
    assert e.reason == FailoverReason.UNKNOWN
    assert e.policy == RetryPolicy.RETRY
