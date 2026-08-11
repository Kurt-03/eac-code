"""Tests for F-block features (F.18-F.22)."""

from eaccode.agent.runtime_helpers import summarize_reasoning
from eaccode.config.providers import ProviderConfig, SecretStr


def test_summarize_reasoning():
    assert summarize_reasoning("short") == "short"
    long_text = "word " * 100
    summary = summarize_reasoning(long_text)
    assert len(summary) <= 161
    assert summary.endswith("…")
    assert "  " not in summarize_reasoning("a  b\n c")  # collapsed whitespace


def _provider(reasoning: str = "auto") -> ProviderConfig:
    return ProviderConfig(
        name="opencode-go", api_key=SecretStr("k"), model="m",
        reasoning=reasoning,
    )


def test_provider_reasoning_field_defaults():
    p = _provider()
    assert p.reasoning == "auto"


def _resolver(reasoning: str):
    from eaccode.llm._resolve import _ResolveMixin

    resolver = _ResolveMixin.__new__(_ResolveMixin)
    resolver.default_model = "m"
    resolver.provider_name = "opencode-go"
    resolver.providers = {"opencode-go": _provider(reasoning)}
    return resolver


def test_resolver_reasoning_off_sets_extra_body():
    from eaccode.llm.models import CompletionRequest, Message

    req = CompletionRequest(messages=[Message.user("hi")], max_tokens=10)
    kwargs = _resolver("off")._base_kwargs(req)
    assert kwargs["extra_body"] == {"reasoning": False}


def test_resolver_reasoning_on_sets_extra_body():
    from eaccode.llm.models import CompletionRequest, Message

    req = CompletionRequest(messages=[Message.user("hi")], max_tokens=10)
    kwargs = _resolver("on")._base_kwargs(req)
    assert kwargs["extra_body"] == {"reasoning": True}


def test_resolver_reasoning_auto_leaves_kwargs_alone():
    from eaccode.llm.models import CompletionRequest, Message

    req = CompletionRequest(messages=[Message.user("hi")], max_tokens=10)
    kwargs = _resolver("auto")._base_kwargs(req)
    assert "extra_body" not in kwargs
