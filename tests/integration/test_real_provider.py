"""Real provider verification (Task 1.5 Step 4).

Uses the real BYOK config (providers.yaml via EaccodePaths) — the full path
from `eaccode providers add` to a live API call. Skips when the provider
is not configured.
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
    assert resp.text.strip(), "Empty response from provider"
    assert "OK" in resp.text.upper()
    assert resp.model  # real model id comes back


def test_real_opencode_go_completion():
    client = _client_for("opencode-go")
    resp = client.complete(
        CompletionRequest(
            messages=[Message.user("Antworte nur mit dem Wort: OK")],
            max_tokens=50,
        )
    )
    assert resp.text.strip(), "Empty response from provider"
    assert "OK" in resp.text.upper()
