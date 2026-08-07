"""Tests für den LiteLLM-Client (Task 2.2)."""

import pytest

from eaccode.llm.client import CompletionRequest, LLMClient, TokenUsage
from eaccode.llm.models import Message, ToolCall


@pytest.fixture
def mock_completion(monkeypatch):
    """Replaces the completion reference bound in the client with a mock.

    Important: `from litellm import completion` binds the function at import time —
    so patch `eaccode.llm.client.completion` here, not litellm.completion.
    """
    import litellm

    def fake_completion(model, messages, **kwargs):
        assert model == "minimax/MiniMax-M2"  # prefix resolution must be correct
        return litellm.ModelResponse.model_validate({
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",
                        "tool_calls": None,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "model": model,
        })

    monkeypatch.setattr("eaccode.llm.client.completion", fake_completion)
    return fake_completion


def test_client_simple_completion(mock_completion, tmp_path):
    client = LLMClient(default_model="MiniMax-M2", providers_file=tmp_path / "p.yaml",
                       provider_name="minimax")
    req = CompletionRequest(messages=[Message.user("Hi")])
    resp = client.complete(req)
    assert resp.text == "Hello!"
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 5
    assert resp.stop_reason == "stop"


def test_client_tool_call_parsing(monkeypatch, tmp_path):
    import litellm

    def fake_completion(model, messages, **kwargs):
        return litellm.ModelResponse.model_validate({
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "reading file...",
                        "tool_calls": [
                            {
                                "id": "t1",
                                "type": "function",
                                "function": {
                                    "name": "read",
                                    "arguments": '{"path": "foo.py", "offset": 5}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_use",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "model": model,
        })

    monkeypatch.setattr("eaccode.llm.client.completion", fake_completion)
    client = LLMClient(default_model="MiniMax-M2", providers_file=tmp_path / "p.yaml",
                       provider_name="minimax")
    resp = client.complete(CompletionRequest(messages=[Message.user("read foo.py")]))
    assert len(resp.tool_calls) == 1
    tc: ToolCall = resp.tool_calls[0]
    assert tc.id == "t1"
    assert tc.name == "read"
    assert tc.arguments == {"path": "foo.py", "offset": 5}
    assert resp.stop_reason == "tool_use"


def test_token_usage_accumulates():
    u = TokenUsage(input_tokens=10, output_tokens=5, cost_usd=0.1)
    u += TokenUsage(input_tokens=20, output_tokens=10, cost_usd=0.2)
    assert u.input_tokens == 30
    assert u.output_tokens == 15
    assert u.cost_usd == pytest.approx(0.3)


def test_messages_convert_to_litellm_format(tmp_path):
    client = LLMClient(
        default_model="m", providers_file=tmp_path / "p.yaml", provider_name="minimax"
    )
    msgs = [
        Message.system("sys"),
        Message.user("hello"),
        Message.assistant_with_tool_calls(
            [], [ToolCall(id="t1", name="bash", arguments={"command": "ls"})]
        ),
        Message.tool_result("t1", "file1\nfile2"),
    ]
    out = client._to_litellm_messages(msgs, system=None)
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[1]["role"] == "user"
    assert out[2]["role"] == "assistant"
    assert out[2]["tool_calls"][0]["function"]["name"] == "bash"
    assert out[3]["role"] == "tool"
    assert out[3]["tool_call_id"] == "t1"


def test_custom_endpoint_passes_credentials_explicitly(tmp_path):
    """Custom OpenAI-compatible endpoints need api_key/api_base per request —
    LiteLLM only knows OPENAI_API_KEY otherwise (Task 1.5 finding)."""
    from eaccode.config.providers import ProviderConfig, save_providers

    save_providers(
        [
            ProviderConfig(
                name="opencode-go",
                api_key="oc-secret",
                model="deepseek-v4-flash",
                base_url="https://opencode.ai/zen/go/v1",
            )
        ],
        tmp_path / "p.yaml",
    )
    client = LLMClient(
        default_model="deepseek-v4-flash",
        providers_file=tmp_path / "p.yaml",
        provider_name="opencode-go",
    )
    req = CompletionRequest(messages=[Message.user("hi")])
    kwargs = client._base_kwargs(req)
    assert kwargs["model"] == "openai/deepseek-v4-flash"
    assert kwargs["api_key"] == "oc-secret"
    assert kwargs["api_base"] == "https://opencode.ai/zen/go/v1"


def test_native_provider_passes_key_only(tmp_path):
    from eaccode.config.providers import ProviderConfig, save_providers

    save_providers(
        [ProviderConfig(name="minimax", api_key="mk-secret", model="MiniMax-M3")],
        tmp_path / "p.yaml",
    )
    client = LLMClient(
        default_model="MiniMax-M3",
        providers_file=tmp_path / "p.yaml",
        provider_name="minimax",
    )
    kwargs = client._base_kwargs(CompletionRequest(messages=[Message.user("hi")]))
    assert kwargs["model"] == "minimax/MiniMax-M3"
    assert kwargs["api_key"] == "mk-secret"
    assert "api_base" not in kwargs  # native provider: no base URL needed


def test_tools_converted_to_openai_format(tmp_path):
    """MiniMax rejected our tools with 'invalid tool type' (2013): it expects
    the OpenAI format (type: function). LiteLLM converts OpenAI → Anthropic
    automatically, but not the other way around — so we always send OpenAI."""
    from eaccode.config.providers import ProviderConfig, save_providers

    save_providers(
        [ProviderConfig(name="minimax", api_key="mk", model="MiniMax-M3")],
        tmp_path / "p.yaml",
    )
    client = LLMClient(
        default_model="MiniMax-M3",
        providers_file=tmp_path / "p.yaml",
        provider_name="minimax",
    )
    req = CompletionRequest(
        messages=[Message.user("hi")],
        tools=[
            {
                "name": "read",
                "description": "Read a file",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            }
        ],
    )
    kwargs = client._base_kwargs(req)
    tools = kwargs["tools"]
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "read"
    assert tools[0]["function"]["parameters"]["properties"]["path"]["type"] == "string"


def test_fallback_chain_used_on_retryable_failure(tmp_path, monkeypatch):
    """After retries are exhausted, the client falls back to the next
    provider in the chain (Hermes pattern, Task 2.5)."""
    import litellm

    from eaccode.config.providers import ProviderConfig, save_providers
    from eaccode.llm.model_switch import FallbackChain

    save_providers(
        [
            ProviderConfig(name="minimax", api_key="mk", model="MiniMax-M3"),
            ProviderConfig(name="opencode-go", api_key="oc", model="deepseek-v4-flash",
                           base_url="https://opencode.ai/zen/go/v1"),
        ],
        tmp_path / "p.yaml",
    )
    calls: list[str] = []

    def fake_completion(model, messages, **kwargs):
        calls.append(model)
        if "minimax" in model:
            raise litellm.RateLimitError(
                model=model,
                message="rate limited",
                llm_provider="minimax",
                response=litellm.ModelResponse(),
            )
        return litellm.ModelResponse.model_validate({
            "choices": [{"message": {"role": "assistant", "content": "from fallback"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "model": model,
        })

    monkeypatch.setattr("eaccode.llm.client.completion", fake_completion)
    client = LLMClient(
        default_model="MiniMax-M3",
        providers_file=tmp_path / "p.yaml",
        provider_name="minimax",
        fallback_chain=FallbackChain([("opencode-go", "deepseek-v4-flash")]),
    )
    resp = client.complete(CompletionRequest(messages=[Message.user("hi")]))
    assert resp.text == "from fallback"
    assert calls[-1] == "openai/deepseek-v4-flash"  # letzter Versuch lief auf dem Fallback


def test_stream_async_thread_producer(tmp_path, monkeypatch):
    """The stream() producer runs in a thread — the event loop stays live.

    Regression test for the REPL freeze: litellm streaming is synchronous;
    iterating its generator inline would block the UI for seconds per chunk.
    """
    import time

    import litellm

    from eaccode.config.providers import ProviderConfig, save_providers
    from eaccode.llm.client import LLMClient, ReasoningDelta
    from eaccode.llm.models import Message, ToolCall

    save_providers(
        [ProviderConfig(name="minimax", api_key="mk", model="MiniMax-M3")],
        tmp_path / "p.yaml",
    )

    def chunk(content, delta=None, tool_calls=None):
        return litellm.ModelResponse.model_validate({
            "choices": [{
                "delta": {
                    "role": "assistant",
                    "content": delta,
                    "tool_calls": tool_calls,
                }
            }]
        })

    def fake_completion(model, messages, **kwargs):
        assert kwargs.get("stream") is True
        time.sleep(0.05)  # simulate a slow provider
        yield chunk("t", delta="Hel")
        yield chunk("t", delta="lo")
        yield chunk("t", delta="", tool_calls=[{
            "index": 0, "id": "c1", "function": {"name": "read", "arguments": '{"path": "x"}'},
        }])

    monkeypatch.setattr("eaccode.llm.client.completion", fake_completion)
    client = LLMClient(
        default_model="MiniMax-M3",
        providers_file=tmp_path / "p.yaml",
        provider_name="minimax",
    )

    async def run():
        import asyncio

        items = []
        async for item in client.stream(
            CompletionRequest(messages=[Message.user("hi")], stream=True)
        ):
            items.append(item)
        return items

    import asyncio as _aio

    items = _aio.run(run())
    texts = [i for i in items if isinstance(i, str)]
    tools = [i for i in items if isinstance(i, ToolCall)]
    assert "".join(texts) == "Hello"
    assert len(tools) == 1
    assert tools[0].name == "read"
    assert tools[0].arguments == {"path": "x"}
