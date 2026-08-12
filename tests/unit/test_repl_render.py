"""P7 (v0.7.2): plain-text event rendering for the classic REPL."""

from eaccode.agent.runner import AgentEvent
from eaccode.ui.messages import (
    banner,
    plain_error,
    plain_info,
    plain_warn,
    render_event_plain,
)


def test_plain_helpers_have_brackets():
    assert plain_info("hello").startswith("[ i ]")
    assert plain_warn("careful").startswith("[ ! ]")
    assert plain_error("bad").startswith("[ X ]")


def test_banner_includes_version():
    text = banner()
    assert "eaccode" in text
    assert "/" in text  # hint


def test_render_tool_call_summary():
    ev = AgentEvent(kind="tool_call", payload={
        "id": "x1", "name": "bash", "arguments": {"command": "ls -la"},
    })
    out = render_event_plain(ev)
    assert "bash" in out
    assert "ls -la" in out


def test_render_tool_result_ok():
    ev = AgentEvent(kind="tool_result", payload={
        "id": "x", "name": "read", "content": "line1\nline2", "is_error": False,
    })
    out = render_event_plain(ev)
    assert "read" in out
    assert "✓" in out
    assert "line1" in out


def test_render_tool_result_error():
    ev = AgentEvent(kind="tool_result", payload={
        "id": "x", "name": "bash", "content": "exit 1", "is_error": True,
    })
    out = render_event_plain(ev)
    assert "✗" in out


def test_render_permission_prompt():
    ev = AgentEvent(kind="permission", payload={
        "id": 3, "tool": "write", "arguments": {"path": "a.py"},
        "question": "Allow write?",
    })
    out = render_event_plain(ev)
    assert "Allow write?" in out
    assert "(y/a/n/p)" in out


def test_render_text_event_is_empty_inline():
    """text events are rendered inline, not via render_event_plain."""
    ev = AgentEvent(kind="text", payload={"delta": "hello"})
    assert render_event_plain(ev) == ""


def test_render_done_returns_empty():
    ev = AgentEvent(kind="done")
    assert render_event_plain(ev) == ""
