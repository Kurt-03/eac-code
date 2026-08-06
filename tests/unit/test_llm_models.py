"""Tests für die vendor-neutralen Message-Modelle (Task 2.1)."""
from eaccode.llm.models import Message, Role, TextContent, ToolCall


def test_message_text_user():
    m = Message.user("Hello")
    assert m.role == Role.USER
    assert m.content[0].text == "Hello"


def test_message_system():
    m = Message.system("You are eaccode")
    assert m.role == Role.SYSTEM
    assert m.content[0].text == "You are eaccode"


def test_message_assistant_plain():
    m = Message.assistant("Hi there")
    assert m.role == Role.ASSISTANT
    assert m.content[0].text == "Hi there"
    assert m.tool_calls is None


def test_assistant_with_tool_calls():
    m = Message.assistant_with_tool_calls(
        [TextContent(text="Let me read that file")],
        [ToolCall(id="t1", name="read", arguments={"path": "foo.py"})],
    )
    assert m.role == Role.ASSISTANT
    assert m.tool_calls is not None
    assert m.tool_calls[0].name == "read"
    assert m.tool_calls[0].arguments["path"] == "foo.py"


def test_tool_result_message():
    m = Message.tool_result("t1", "file contents here", is_error=False)
    assert m.role == Role.TOOL
    assert m.tool_call_id == "t1"
    assert m.content[0].text == "file contents here"
    assert m.is_error is False


def test_tool_result_error_flag():
    m = Message.tool_result("t2", "permission denied", is_error=True)
    assert m.is_error is True


def test_message_roundtrip_via_json():
    """Sessions speichern Messages als JSON — Roundtrip muss stabil sein."""
    m = Message.assistant_with_tool_calls(
        [TextContent(text="working")],
        [ToolCall(id="x1", name="bash", arguments={"command": "ls"})],
    )
    data = m.model_dump(mode="json")
    restored = Message.model_validate(data)
    assert restored == m
