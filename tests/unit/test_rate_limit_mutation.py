"""Tests for rate-limit tracking (H.8) and mutation verification (H.5)."""

from eaccode.llm.rate_limit import (
    RateLimitState,
    format_rate_limit_compact,
    parse_rate_limit_headers,
)
from eaccode.tools.result_classification import file_mutation_result_landed


class TestRateLimit:
    def test_parse_full_headers(self):
        headers = {
            "x-ratelimit-limit-requests": "60",
            "x-ratelimit-remaining-requests": "42",
            "x-ratelimit-limit-tokens": "100000",
            "x-ratelimit-remaining-tokens": "50000",
            "x-ratelimit-reset-requests": "30",
        }
        state = parse_rate_limit_headers(headers)
        assert state.requests.limit == 60
        assert state.requests.remaining == 42
        assert state.tokens.limit == 100000
        assert state.tokens.remaining == 50000
        assert state.requests.reset_seconds == 30.0
        assert state.any_data is True

    def test_parse_empty_headers(self):
        state = parse_rate_limit_headers({})
        assert state.any_data is False

    def test_parse_none(self):
        state = parse_rate_limit_headers(None)
        assert state.any_data is False

    def test_parse_garbage_values(self):
        headers = {"x-ratelimit-limit-requests": "abc", "x-ratelimit-remaining-tokens": ""}
        state = parse_rate_limit_headers(headers)
        assert state.requests.limit == 0  # safe default

    def test_compact_format(self):
        headers = {"x-ratelimit-limit-requests": "60", "x-ratelimit-remaining-requests": "42"}
        text = format_rate_limit_compact(parse_rate_limit_headers(headers))
        assert "req 42/60" in text

    def test_compact_empty(self):
        assert format_rate_limit_compact(RateLimitState()) == ""


class TestMutationVerify:
    def test_write_result_lands(self, tmp_path):
        path = tmp_path / "f.txt"
        path.write_text("ok", encoding="utf-8")
        result = f"Wrote 2 bytes to {path}"
        assert file_mutation_result_landed("write", result) is True

    def test_write_result_missing_file(self, tmp_path):
        path = tmp_path / "ghost.txt"  # does not exist
        result = f"Wrote 2 bytes to {path}"
        assert file_mutation_result_landed("write", result) is False

    def test_write_result_no_match(self):
        assert file_mutation_result_landed("write", "Something happened") is False

    def test_edit_result_lands(self, tmp_path):
        path = tmp_path / "e.py"
        path.write_text("x", encoding="utf-8")
        assert file_mutation_result_landed("edit", f"Edited {path}") is True

    def test_other_tool_success(self):
        assert file_mutation_result_landed("bash", "exit code 0 output") is True

    def test_other_tool_error(self):
        assert file_mutation_result_landed("bash", "Error: command not found") is False

    def test_empty_result(self):
        assert file_mutation_result_landed("write", None) is False
