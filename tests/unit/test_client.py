"""Tests für den LiteLLM-Client (Task 2.2)."""
from pathlib import Path

import pytest

from eaccode.llm.client import CompletionRequest, LLMClient, TokenUsage
from eaccode.llm.models import Message, ToolCall


@pytest.fixture
def mock_completion(monkeypatch):
    """Ersetzt die im Client gebundene completion-Referenz durch ein Mock.

    Wichtig: `from litellm import completion` bindet die Funktion beim Import —
    deshalb hier `eaccode.llm.client.completion` patchen, nicht litellm.completion.
    """
    import litellm

    def fake_completion(model, messages, **kwargs):
        assert model == "minimax/MiniMax-M2"  # Prefix-Auflösung muss stimmen
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
    client = LLMClient(default_model="m", providers_file=tmp_path / "p.yaml", provider_name="minimax")
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
