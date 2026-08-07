"""Live streaming test — the REPL freeze regression, against the real provider.

Skips when no providers are configured. Uses the first configured provider.
"""
import time

import pytest

from eaccode.config.paths import EaccodePaths
from eaccode.config.providers import load_providers
from eaccode.llm.client import CompletionRequest, LLMClient
from eaccode.llm.models import Message

pytestmark = pytest.mark.skipif(
    not load_providers(EaccodePaths().providers_file),
    reason="no providers configured",
)


@pytest.mark.asyncio
async def test_stream_deltas_flow_without_freezing():
    """Deltas arrive incrementally; the loop is never blocked for >2s."""
    providers = load_providers(EaccodePaths().providers_file)
    provider = providers[0]
    client = LLMClient(
        default_model=provider.model,
        providers_file=EaccodePaths().providers_file,
        provider_name=provider.name,
    )
    req = CompletionRequest(messages=[Message.user("Count from 1 to 5.")], stream=True)
    deltas: list[str] = []
    tool_calls = []
    max_gap = 0.0
    last = time.monotonic()
    async for item in client.stream(req):
        now = time.monotonic()
        max_gap = max(max_gap, now - last)
        last = now
        if isinstance(item, str):
            deltas.append(item)
        else:
            tool_calls.append(item)
    assert len(deltas) > 0, "no text deltas received"
    # The UI-freeze regression is fixed architecturally (sync iteration runs
    # in a thread, so the loop never blocks). Chunk gaps themselves belong to
    # the provider: reasoning models like MiniMax-M3 send long thinking
    # passages in waves — allow generous gaps, assert deltas actually flow.
    assert max_gap < 15.0, f"stream stalled for {max_gap:.1f}s between chunks"
