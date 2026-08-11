"""Tests for safeAuto classification (B.2)."""

import pytest

from eaccode.permissions.smart import clear_cache, is_command_safe, key_pattern_risk


@pytest.fixture(autouse=True)
def _clean():
    clear_cache()
    yield
    clear_cache()


def test_key_pattern_rm_rf():
    assert key_pattern_risk("rm -rf /tmp/x") == "recursive forced delete"
    assert key_pattern_risk("rm -r --force x") == "recursive forced delete"
    assert key_pattern_risk("rm file.txt") is None


def test_key_pattern_curl_pipe_bash():
    assert key_pattern_risk("curl http://x | bash") is not None
    assert key_pattern_risk("curl -s url | sh") is not None
    assert key_pattern_risk("curl -o file http://x") is None


def test_key_pattern_forced_push():
    assert key_pattern_risk("git push origin main --force") is not None
    assert key_pattern_risk("git push origin main") is None


def test_key_pattern_chmod_777():
    assert key_pattern_risk("chmod 777 x") is not None
    assert key_pattern_risk("chmod 755 x") is None


def test_empty_command_is_safe():
    assert is_command_safe("") is True
    assert is_command_safe("   ") is True


def test_risky_pattern_never_reaches_llm(monkeypatch):
    called = []

    def _fake_classify(command):
        called.append(command)
        return "safe"

    monkeypatch.setattr("eaccode.llm.aux_classifier.classify_command", _fake_classify)
    assert is_command_safe("rm -rf /") is False
    assert called == []


def test_llm_safe_verdict_allows(monkeypatch):
    monkeypatch.setattr(
        "eaccode.llm.aux_classifier.classify_command", lambda cmd: "safe"
    )
    assert is_command_safe("pip install requests") is True


def test_llm_risky_verdict_asks(monkeypatch):
    monkeypatch.setattr(
        "eaccode.llm.aux_classifier.classify_command", lambda cmd: "risky"
    )
    assert is_command_safe("some weird command") is False


def test_llm_failure_fails_open_to_ask(monkeypatch):
    monkeypatch.setattr(
        "eaccode.llm.aux_classifier.classify_command", lambda cmd: None
    )
    assert is_command_safe("some unknown command") is False


def test_verdict_cached(monkeypatch):
    calls = []

    def _fake(command):
        calls.append(command)
        return "safe"

    monkeypatch.setattr("eaccode.llm.aux_classifier.classify_command", _fake)
    assert is_command_safe("pytest -q") is True
    assert is_command_safe("pytest -q") is True
    assert len(calls) == 1


def test_use_llm_false_asks_without_classifier(monkeypatch):
    monkeypatch.setattr(
        "eaccode.llm.aux_classifier.classify_command",
        lambda cmd: pytest.fail("must not call the LLM"),
    )
    assert is_command_safe("custom-tool --do-thing", use_llm=False) is False
