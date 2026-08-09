"""Per-reasoning-model stale-timeout floor (Phase H.4).

Ported from Hermes' ``agent/reasoning_timeouts.py``. Reasoning models
(those emitting extended thinking before the first content token)
routinely exceed default chat-model stale detectors. MiniMax-M3 can
think >180s on a hard prompt; without a floor the client would kill a
legitimate request as "stale".
"""

from __future__ import annotations

# model-substring → stale-timeout floor in seconds.
# The default chat-model stale detector is 180s (stream) / 90s (non-stream);
# reasoning models get a higher floor so thinking is never mistaken for a
# dead connection.
_REASONING_TIMEOUT_FLOORS: dict[str, float] = {
    "minimax": 600.0,       # MiniMax-M3 spends 1k-3k tokens thinking
    "deepseek-r": 300.0,    # deepseek-reasoner family
    "deepseek-reasoner": 300.0,
    "qwen-r": 300.0,
    "qwen3-r": 300.0,
    "r1": 300.0,            # DeepSeek-R1 / derivative names
    "o1": 600.0,            # OpenAI o-series
    "o3": 600.0,
    "o4": 600.0,
    "kimi-k": 300.0,        # Kimi K-series (thinking variants)
    "thinking": 300.0,      # generic "thinking mode" markers
}


def get_reasoning_stale_timeout_floor(model: str) -> float | None:
    """Return the stale-timeout floor for a known reasoning model, else
    None (callers keep their default detector)."""
    if not model:
        return None
    lowered = model.lower()
    for marker, floor in _REASONING_TIMEOUT_FLOORS.items():
        if marker in lowered:
            return floor
    return None
