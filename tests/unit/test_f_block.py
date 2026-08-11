"""Tests for F-block features (F.18-F.22)."""

import pytest
from pydantic import BaseModel

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
    from eaccode.llm.client import CompletionRequest
    from eaccode.llm.models import Message

    req = CompletionRequest(messages=[Message.user("hi")], max_tokens=10)
    kwargs = _resolver("off")._base_kwargs(req)
    assert kwargs["extra_body"] == {"reasoning": False}


def test_resolver_reasoning_on_sets_extra_body():
    from eaccode.llm.client import CompletionRequest
    from eaccode.llm.models import Message

    req = CompletionRequest(messages=[Message.user("hi")], max_tokens=10)
    kwargs = _resolver("on")._base_kwargs(req)
    assert kwargs["extra_body"] == {"reasoning": True}


def test_resolver_reasoning_auto_leaves_kwargs_alone():
    from eaccode.llm.client import CompletionRequest
    from eaccode.llm.models import Message

    req = CompletionRequest(messages=[Message.user("hi")], max_tokens=10)
    kwargs = _resolver("auto")._base_kwargs(req)
    assert "extra_body" not in kwargs


# ---------------------------------------------------------------- F.25


def test_redact_jwt():
    from eaccode.security.redact import redact_secrets

    jwt = ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
           "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")
    assert "[REDACTED]" in redact_secrets(f"token={jwt}")
    assert jwt not in redact_secrets(jwt)


def test_redact_pem_block():
    from eaccode.security.redact import redact_secrets

    pem = ("-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEF\n"
           "-----END PRIVATE KEY-----")
    assert "[REDACTED]" in redact_secrets(pem)


def test_redact_sk_proj():
    from eaccode.security.redact import redact_secrets

    key = "sk-proj-abcdefghijklmnopqrstuvwxyz123456"
    assert key not in redact_secrets(f"key: {key}")


# ---------------------------------------------------------------- F.26


def test_cleanup_old_checkpoints(tmp_path):
    import os

    from eaccode.tools.checkpoints import (
        checkpoint_dir,
        cleanup_old_checkpoints,
    )

    cdir = checkpoint_dir(tmp_path)
    cdir.mkdir(parents=True)
    old = cdir / "old.json"
    old.write_text("x")
    old_time = os.path.getmtime(old) - 20 * 86400
    os.utime(old, (old_time, old_time))
    fresh = cdir / "fresh.json"
    fresh.write_text("x")
    assert cleanup_old_checkpoints(tmp_path, max_age_days=7) == 1
    assert not old.exists()
    assert fresh.exists()


# ---------------------------------------------------------------- F.24


@pytest.mark.asyncio
async def test_verify_on_stop_retries_once_then_raises(tmp_path):
    from eaccode.agent.loop import AgentConfig, AgentLoop
    from eaccode.config.settings import PermissionMode
    from eaccode.llm.client import CompletionResponse, TokenUsage
    from eaccode.llm.models import Message
    from eaccode.permissions.policy import PolicyEngine
    from eaccode.permissions.rules import RuleSet
    from eaccode.tools.base import ToolRegistry

    class EmptyClient:
        def __init__(self):
            self.calls = 0

        def complete(self, req):
            self.calls += 1
            return CompletionResponse(
                text="   ", tool_calls=[], stop_reason="end_turn",
                usage=TokenUsage(), model="fake",
            )

    client = EmptyClient()
    loop = AgentLoop(
        client, ToolRegistry(),
        PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet()),
        AgentConfig(workdir=tmp_path, max_turns=5),
    )
    with pytest.raises(RuntimeError, match="verify_on_stop"):
        await loop.run([Message.user("hi")])
    assert client.calls == 2  # initial empty answer + one retry
    assert loop._empty_response_retries == 1


@pytest.mark.asyncio
async def test_verify_on_stop_recovers_with_second_answer(tmp_path):
    from eaccode.agent.loop import AgentConfig, AgentLoop
    from eaccode.config.settings import PermissionMode
    from eaccode.llm.client import CompletionResponse, TokenUsage
    from eaccode.llm.models import Message
    from eaccode.permissions.policy import PolicyEngine
    from eaccode.permissions.rules import RuleSet
    from eaccode.tools.base import ToolRegistry

    class FlakyClient:
        def __init__(self):
            self.calls = 0

        def complete(self, req):
            self.calls += 1
            text = "real answer" if self.calls > 1 else "  "
            return CompletionResponse(
                text=text, tool_calls=[], stop_reason="end_turn",
                usage=TokenUsage(), model="fake",
            )

    loop = AgentLoop(
        FlakyClient(), ToolRegistry(),
        PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet()),
        AgentConfig(workdir=tmp_path, max_turns=5),
    )
    result = await loop.run([Message.user("hi")])
    assert result.final_text == "real answer"


# ---------------------------------------------------------------- F.32


def test_classify_transient():
    from eaccode.agent.error_classifier import classify_error, should_retry

    assert classify_error(RuntimeError("rate limit exceeded")) == "transient"
    assert classify_error(TimeoutError("timed out")) == "transient"
    assert classify_error(RuntimeError("500 server error")) == "transient"
    assert should_retry(RuntimeError("rate limit"), 0) is True
    assert should_retry(RuntimeError("rate limit"), 2) is False


def test_classify_permanent():
    from eaccode.agent.error_classifier import classify_error, should_retry

    assert classify_error(RuntimeError("invalid api key")) == "permanent"
    assert classify_error(RuntimeError("401 unauthorized")) == "permanent"
    assert should_retry(RuntimeError("invalid api key"), 0) is False


def test_classify_needs_input():
    from eaccode.agent.error_classifier import classify_error

    assert classify_error(RuntimeError("permission required")) == "needs_input"
    assert classify_error(RuntimeError("missing required field")) == "needs_input"


# ---------------------------------------------------------------- F.29


def test_thread_silence_context():
    from eaccode.agent.thread_silence import is_worker_silent, thread_silenced

    assert is_worker_silent() is False
    with thread_silenced():
        assert is_worker_silent() is True
    assert is_worker_silent() is False


# ---------------------------------------------------------------- F.36


def test_resolver_timeout_kwarg():
    from eaccode.llm._resolve import _ResolveMixin
    from eaccode.llm.client import CompletionRequest
    from eaccode.llm.models import Message

    resolver = _ResolveMixin.__new__(_ResolveMixin)
    resolver.default_model = "m"
    resolver.provider_name = "opencode-go"
    resolver.providers = {"opencode-go": _provider("auto")}
    resolver.timeout = 42.0
    req = CompletionRequest(messages=[Message.user("hi")], max_tokens=10)
    assert resolver._base_kwargs(req)["timeout"] == 42.0
    resolver.timeout = None
    assert "timeout" not in resolver._base_kwargs(req)


@pytest.mark.asyncio
async def test_estop_flag_stops_tool_execution(tmp_path):
    import asyncio

    from eaccode.agent.loop import AgentConfig, AgentLoop
    from eaccode.config.settings import PermissionMode
    from eaccode.llm.client import CompletionResponse, TokenUsage
    from eaccode.llm.models import Message, ToolCall
    from eaccode.permissions.policy import PolicyEngine
    from eaccode.permissions.rules import RuleSet
    from eaccode.tools.base import Tool, ToolRegistry, ToolResult

    ran = []

    class BoomInput(BaseModel):
        pass

    class BoomTool(Tool):
        name = "boom"
        description = "boom"
        input_model = BoomInput
        requires_permission = False
        tool_class = None

        async def run(self, input, ctx):
            ran.append("ran")
            return ToolResult(content="x")

    class ToolClient:
        def complete(self, req):
            return CompletionResponse(
                text="", tool_calls=[ToolCall(id="1", name="boom",
                                              arguments={})],
                stop_reason="tool_calls", usage=TokenUsage(), model="fake",
            )

    reg = ToolRegistry()
    reg.register(BoomTool())
    flag = asyncio.Event()
    loop = AgentLoop(
        ToolClient(), reg,
        PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet()),
        AgentConfig(workdir=tmp_path, max_turns=2, estop_flag=flag),
    )
    flag.set()  # user hit Esc before/while the tool ran
    with pytest.raises(InterruptedError):
        await loop.run([Message.user("go")])
    assert ran == []
