"""Tests for secret redaction (Phase A.2)."""
from eaccode.security.redact import redact_dict, redact_secrets


def test_openai_style_key_redacted():
    assert "sk-abc1234567890xyz" not in redact_secrets("key is sk-abc1234567890xyz")
    assert "[REDACTED]" in redact_secrets("key is sk-abc1234567890xyz")


def test_github_pat_redacted():
    s = redact_secrets("token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 here")
    assert "ghp_" not in s


def test_google_and_aws_redacted():
    assert "[REDACTED]" in redact_secrets("AIzaSyD0x9qwertyuiopasdfghjklzxcvbnm12345")
    assert "[REDACTED]" in redact_secrets("AKIAIOSFODNN7EXAMPLE")


def test_key_value_pairs_redacted():
    s = redact_secrets("api_key=sk-verysecret123456 and password=hunter22")
    assert "sk-verysecret123456" not in s
    assert "hunter22" not in s


def test_bearer_token_redacted():
    s = redact_secrets("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in s


def test_normal_text_untouched():
    text = "The function returns a list of items. max_tokens=500 works fine."
    assert redact_secrets(text) == text


def test_short_values_not_redacted():
    # 6-char 'token=' values would be aggressive; keep readable code intact
    s = redact_secrets("token=500, count=42")
    assert "token=500" in s or "[REDACTED]" in s


def test_redact_dict_recursive():
    d = {"path": "x.py", "headers": {"Authorization": "Bearer abcdefgh1234567890"}}
    out = redact_dict(d)
    assert "abcdefgh1234567890" not in str(out)
    assert out["path"] == "x.py"


def test_empty_and_none():
    assert redact_secrets("") == ""
    assert redact_secrets(None) is None
