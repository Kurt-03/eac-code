"""Tests for the aux classifier (B.1) — parsing and fail-open behavior."""

import pytest

from eaccode.llm.aux_classifier import parse_verdict


def test_parse_verdict_plain_json():
    assert parse_verdict('{"verdict": "safe", "reason": "ok"}') == "safe"


def test_parse_verdict_fenced():
    assert parse_verdict('```json\n{"verdict": "risky"}\n```') == "risky"


def test_parse_verdict_noise_around_json():
    text = 'Here you go:\n{"verdict": "safe", "reason": "read only"} thanks!'
    assert parse_verdict(text) == "safe"


def test_parse_verdict_invalid():
    assert parse_verdict("I cannot classify this.") is None
    assert parse_verdict('{"verdict": "maybe"}') is None


def test_parse_verdict_case_insensitive():
    assert parse_verdict('{"verdict": "SAFE"}') == "safe"


@pytest.mark.asyncio
async def test_classify_unavailable_provider_returns_none(monkeypatch):
    from eaccode.llm import aux_classifier

    monkeypatch.setattr(aux_classifier, "_classifier_provider", lambda: None)
    assert aux_classifier.classify_command("ls") is None


def test_classify_llm_error_returns_none(monkeypatch):
    from eaccode.llm import aux_classifier

    class _Provider:
        model = "m"
        api_key = None
        base_url = None
        extra = None

    monkeypatch.setattr(aux_classifier, "_classifier_provider", lambda: _Provider())

    def _boom(**kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("litellm.completion", _boom)
    assert aux_classifier.classify_command("ls") is None
