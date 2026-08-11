"""Tests for the session title generator (D.1/D.2)."""

import pytest

from eaccode.sessions.titles import (
    derive_title,
    llm_title_async,
    should_upgrade,
)


def test_derive_title_truncates():
    assert derive_title("fix the build pipeline now please") == \
        "fix the build pipeline now please"
    long_text = "x" * 100
    title = derive_title(long_text)
    assert len(title) <= 41  # 40 + ellipsis
    assert title.endswith("…")
    assert derive_title("") == "untitled"
    assert derive_title("   ") == "untitled"


def test_provenance_order():
    assert should_upgrade("derived", "llm") is True
    assert should_upgrade("derived", "user") is True
    assert should_upgrade("llm", "user") is True
    assert should_upgrade("user", "llm") is False
    assert should_upgrade("user", "derived") is False
    assert should_upgrade("llm", "derived") is False


@pytest.mark.asyncio
async def test_llm_title_failure_returns_none(monkeypatch):
    async def _boom(**kwargs):
        raise RuntimeError("network")

    monkeypatch.setattr("litellm.acompletion", _boom)
    assert await llm_title_async("hello") is None


@pytest.mark.asyncio
async def test_llm_title_success(monkeypatch):
    class _Resp:
        choices = [type("C", (), {"message": type("M", (), {"content": '"Fix build"'})})]

    async def _fake(**kwargs):
        return _Resp()

    monkeypatch.setattr("litellm.acompletion", _fake)
    assert await llm_title_async("hello", provider=None) == "Fix build"
