"""Tests for token counting (Task 2.3)."""
from eaccode.llm.models import Message, ToolCall
from eaccode.llm.tokens import count_message_tokens, model_context_window


def test_count_short_messages():
    msgs = [Message.user("Hello world this is a test")]
    n = count_message_tokens(msgs)
    assert n > 0
    assert n < 50


def test_count_grows_with_content():
    short = count_message_tokens([Message.user("hi")])
    long = count_message_tokens([Message.user("x" * 5000)])
    assert long > short


def test_tool_calls_counted():
    with_calls = count_message_tokens(
        [Message.assistant_with_tool_calls(
            [], [ToolCall(id="t1", name="read", arguments={"path": "a" * 200})]
        )]
    )
    without = count_message_tokens([Message.assistant("")])
    assert with_calls > without


def test_context_window_sizes():
    assert model_context_window("anthropic/claude-sonnet-4-6") == 200_000
    assert model_context_window("openai/gpt-4o") == 128_000
    assert model_context_window("google/gemini-2.5-pro") == 1_000_000
    assert model_context_window("unbekanntes-modell") == 128_000  # safe default
