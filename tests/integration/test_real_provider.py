"""Real provider verification (Task 1.5 Step 4).

Runs only when the respective API key is set as an env var
(MINIMAX_API_KEY / OPENCODE_GO_API_KEY) — e.g. after:
    eaccode providers add --provider minimax --model MiniMax-M3
"""
import os
from pathlib import Path

import pytest

from eaccode.llm.client import CompletionRequest, LLMClient
from eaccode.llm.models import Message


@pytest.mark.skipif(
    not os.getenv("MINIMAX_API_KEY"),
    reason="requires MINIMAX_API_KEY (eaccode providers add --provider minimax)",
)
def test_real_minimax_completion(tmp_path):
    client = LLMClient(
        default_model="MiniMax-M3",
        providers_file=tmp_path / "none.yaml",
        provider_name="minimax",
    )
    resp = client.complete(
        CompletionRequest(
            messages=[Message.user("Antworte nur mit dem Wort: OK")],
            max_tokens=50,
        )
    )
    assert resp.text.strip(), "Empty response from provider"
    assert "OK" in resp.text.upper()


@pytest.mark.skipif(
    not os.getenv("OPENCODE_GO_API_KEY"),
    reason="requires OPENCODE_GO_API_KEY (eaccode providers add --provider opencode-go)",
)
def test_real_opencode_go_completion(tmp_path):
    client = LLMClient(
        default_model="deepseek-v4-flash",
        providers_file=tmp_path / "none.yaml",
        provider_name="opencode-go",
    )
    resp = client.complete(
        CompletionRequest(
            messages=[Message.user("Antworte nur mit dem Wort: OK")],
            max_tokens=50,
        )
    )
    assert resp.text.strip(), "Leere Antwort vom Provider"
    assert "OK" in resp.text.upper()
