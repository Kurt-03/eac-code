"""Tests for provider-specific thinking (Task 2.4)."""
from eaccode.llm.thinking import EffortLevel, ThinkingMapper


def test_anthropic_budget_mapping():
    m = ThinkingMapper()
    params = m.apply("anthropic/claude-sonnet-4-6", EffortLevel.HIGH)
    assert params["thinking"] == {"type": "enabled", "budget_tokens": 16384}


def test_anthropic_medium_budget():
    m = ThinkingMapper()
    params = m.apply("anthropic/claude-sonnet-4-6", EffortLevel.MEDIUM)
    assert params["thinking"]["budget_tokens"] == 4096


def test_anthropic_haiku_no_thinking():
    m = ThinkingMapper()
    params = m.apply("anthropic/claude-haiku-4-5", EffortLevel.HIGH)
    assert "thinking" not in params  # Haiku does not support extended thinking


def test_openai_reasoning_effort():
    m = ThinkingMapper()
    params = m.apply("openai/o3", EffortLevel.MEDIUM)
    assert params["reasoning_effort"] == "medium"


def test_openai_gpt4o_no_thinking():
    m = ThinkingMapper()
    params = m.apply("openai/gpt-4o", EffortLevel.HIGH)
    assert params == {}  # no reasoning param exists


def test_gemini_thinking_budget():
    m = ThinkingMapper()
    params = m.apply("google/gemini-2.5-pro", EffortLevel.LOW)
    assert params["thinkingConfig"]["thinkingBudget"] == 256


def test_unknown_model_safe_noop():
    m = ThinkingMapper()
    assert m.apply("ollama/qwen3:32b", EffortLevel.HIGH) == {}  # never crash


def test_supports_thinking_flags():
    m = ThinkingMapper()
    assert m.supports_thinking("anthropic/claude-sonnet-4-6") is True
    assert m.supports_thinking("anthropic/claude-haiku-4-5") is False
    assert m.supports_thinking("openai/gpt-4o") is False


def test_stream_reasoning_models():
    """DeepSeek/Qwen deliver reasoning_content in the stream — no request param."""
    m = ThinkingMapper()
    assert m.is_stream_reasoning("deepseek/deepseek-chat") is True
    assert m.is_stream_reasoning("ollama/qwen3:32b") is True
    assert m.is_stream_reasoning("anthropic/claude-sonnet-4-6") is False
    assert m.apply("deepseek/deepseek-chat", EffortLevel.HIGH) == {}
