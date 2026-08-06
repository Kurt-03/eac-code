"""Tests for FTS5 session search (Task 6.6)."""
import pytest

from eaccode.llm.models import Message
from eaccode.sessions.search import search_sessions
from eaccode.sessions.store import SessionStore


@pytest.mark.asyncio
async def test_search_finds_previous_solution(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    await store.save("fix-docker", [
        Message.user("how do I fix docker volumes?"),
        Message.assistant("Mount with -v /host:/container"),
    ])
    await store.save("other", [Message.user("weather")])
    hits = await search_sessions(store, "docker volumes")
    assert len(hits) == 1
    assert hits[0].title == "fix-docker"
    assert "Mount" in hits[0].snippet


@pytest.mark.asyncio
async def test_search_no_hits(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    await store.save("a", [Message.user("nothing here")])
    assert await search_sessions(store, "zzz-nothing-matches") == []


@pytest.mark.asyncio
async def test_search_snippets_highlight_terms(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    await store.save("b", [Message.user("the auth token expires after 3600s")])
    hits = await search_sessions(store, "auth token")
    assert len(hits) == 1
    assert "auth" in hits[0].snippet.lower()
