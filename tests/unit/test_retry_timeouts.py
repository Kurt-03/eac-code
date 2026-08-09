"""Tests for reasoning timeout floors (H.4) and retry utils (H.7)."""

from eaccode.llm.reasoning_timeouts import get_reasoning_stale_timeout_floor
from eaccode.llm.retry_utils import (
    adaptive_rate_limit_backoff,
    jittered_backoff,
    parse_retry_after_seconds,
)


def test_minimax_m3_gets_floor():
    assert get_reasoning_stale_timeout_floor("MiniMax-M3") == 600.0


def test_deepseek_reasoner_gets_floor():
    assert get_reasoning_stale_timeout_floor("deepseek-reasoner") == 300.0


def test_unknown_model_no_floor():
    assert get_reasoning_stale_timeout_floor("gpt-4o") is None
    assert get_reasoning_stale_timeout_floor("") is None
    assert get_reasoning_stale_timeout_floor(None) is None


def test_case_insensitive():
    assert get_reasoning_stale_timeout_floor("MINIMAX-M3") == 600.0


def test_parse_retry_after_seconds_header():
    assert parse_retry_after_seconds("5") == 5.0
    assert parse_retry_after_seconds("0") == 0.0


def test_parse_retry_after_from_headers_dict():
    assert parse_retry_after_seconds({"Retry-After": "12"}) == 12.0
    assert parse_retry_after_seconds({"retry-after": "3"}) == 3.0


def test_parse_retry_after_unknown():
    assert parse_retry_after_seconds(None) is None
    assert parse_retry_after_seconds("not-a-number") is None
    assert parse_retry_after_seconds({}) is None


def test_jittered_backoff_bounds():
    for attempt in range(5):
        d = jittered_backoff(attempt, base=1.0, cap=10.0)
        assert d >= 0.0
        assert d <= 10.0
    # attempt 3 with base 1 → raw 8s, capped at 10.
    assert jittered_backoff(10, base=1.0, cap=10.0) <= 10.0


def test_adaptive_backoff_prefers_retry_after():
    class FakeResponse:
        def __init__(self, headers):
            self.headers = headers

    class FakeError:
        def __init__(self, headers):
            self.response = FakeResponse(headers)

    err = FakeError({"Retry-After": "7"})
    assert adaptive_rate_limit_backoff(err, 0) == 7.0


def test_adaptive_backoff_jittered_without_header():
    # No Retry-After → falls back to jittered backoff (bounded by cap).
    d = adaptive_rate_limit_backoff(object(), 0, base=1.0, cap=5.0)
    assert 0.0 <= d <= 5.0
