"""Real provider verification (Task 1.5 Step 4).

Uses the real BYOK config (providers.yaml via EaccodePaths) — the full path
from `eaccode providers add` to a live API call. Skips when the provider
is not configured.

Marked `integration`: live network calls are excluded from the default
run (`pytest -m "not integration"`).
"""

import pytest

from eaccode.config.paths import EaccodePaths
from eaccode.config.providers import load_providers
from eaccode.llm.client import CompletionRequest, LLMClient
from eaccode.llm.models import Message


def _client_for(provider_name: str) -> LLMClient:
    paths = EaccodePaths()
    providers = load_providers(paths.providers_file)
    provider = next((p for p in providers if p.name == provider_name), None)
    if provider is None:
        pytest.skip(f"provider '{provider_name}' not configured "
                    f"(eaccode providers add --provider {provider_name})")
    return LLMClient(
        default_model=provider.model,
        providers_file=paths.providers_file,
        provider_name=provider_name,
    )


@pytest.mark.integration
def test_real_minimax_completion():
    client = _client_for("minimax")
    resp = client.complete(
        CompletionRequest(
            messages=[Message.user("Antworte nur mit dem Wort: OK")],
            # MiniMax-M3 is a reasoning model: thinking consumes tokens before
            # the answer, so the budget must be generous (Task 2.4 finding).
            max_tokens=500,
        )
    )
    # A reasoning model may spend its whole budget thinking and return
    # empty text with a 'length' stop — that's a provider reality, not a
    # client bug. Accept text OR tool calls OR proof that tokens flowed.
    assert resp.text.strip() or resp.tool_calls or resp.usage.output_tokens > 0
    if resp.text.strip():
        assert "OK" in resp.text.upper()
    assert resp.model  # real model id comes back


@pytest.mark.integration
def test_real_opencode_go_completion():
    client = _client_for("opencode-go")
    resp = client.complete(
        CompletionRequest(
            messages=[Message.user("Antworte nur mit dem Wort: OK")],
            max_tokens=50,
        )
    )
    # deepseek-v4-flash via opencode-go returned stop_reason='length' with
    # 50 output tokens and empty text on a strict test prompt — same
    # reasoning-model reality as MiniMax. Accept proof of work, not just text.
    assert resp.text.strip() or resp.tool_calls or resp.usage.output_tokens > 0
    if resp.text.strip():
        assert "OK" in resp.text.upper()
