"""Tests for the session store (Task 5.2)."""
import pytest

from eaccode.llm.models import Message
from eaccode.sessions.store import SessionStore


@pytest.mark.asyncio
async def test_save_and_load_session(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    msgs = [Message.user("hello"), Message.assistant("hi")]
    sid = await store.save("test-session", msgs, metadata={"cwd": "/tmp"})
    loaded = await store.load(sid)
    assert loaded.title == "test-session"
    assert loaded.messages[0].content[0].text == "hello"
    assert loaded.messages[1].role.value == "assistant"
    assert loaded.metadata["cwd"] == "/tmp"


@pytest.mark.asyncio
async def test_load_missing_raises(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    with pytest.raises(KeyError):
        await store.load("gibt-es-nicht")


@pytest.mark.asyncio
async def test_list_sessions_newest_first(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    await store.save("first", [Message.user("a")])
    await store.save("second", [Message.user("b")])
    sessions = await store.list_sessions()
    assert len(sessions) == 2
    assert sessions[0].title == "second"  # newest first


@pytest.mark.asyncio
async def test_roundtrip_with_tool_calls(tmp_path):
    from eaccode.llm.models import TextContent, ToolCall

    store = SessionStore(tmp_path / "sessions.db")
    msgs = [
        Message.assistant_with_tool_calls(
            [TextContent(text="working")],
            [ToolCall(id="x1", name="bash", arguments={"command": "ls"})],
        )
    ]
    sid = await store.save("tools", msgs)
    loaded = await store.load(sid)
    assert loaded.messages[0].tool_calls[0].name == "bash"
