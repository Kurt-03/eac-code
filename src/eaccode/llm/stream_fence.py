"""Stream single-writer fence (Phase C.4).

Ported from Hermes' ``agent/stream_single_writer.py``. Ctrl+C during a
stream, or a new turn starting while the old producer is still draining,
must never let a stale stream's chunks reach the UI. The fence drops
chunks from a *provably superseded* writer — never from the sole
legitimate one.

The check is best-effort: when the claim machinery is unavailable it
degrades to "no fence" (keep streaming), which is the safe direction.
"""

from __future__ import annotations

import itertools
import threading
from typing import Any

_token_counter = itertools.count(1)
_lock = threading.Lock()


def claim_stream_writer(owner: Any) -> int:
    """Claim the delta sink for the calling stream attempt.

    Stores the token on *owner* (``_stream_writer_token``), so a newer
    claim supersedes older writers even if the caller never stores the
    return value. Returns the monotonically increasing writer token.
    """
    with _lock:
        token = next(_token_counter)
    owner._stream_writer_token = token
    return token


def stream_writer_is_current(owner: Any, token: int) -> bool:
    """True when *token* is still the active writer.

    A falsy token (from a claim that no-oped) means we cannot prove
    supersession, so the stream is treated as current and never fenced.
    """
    if not token:
        return True
    current = getattr(owner, "_stream_writer_token", 0)
    return token == current


def fence_delta(owner: Any, token: int, delta: Any) -> Any | None:
    """Return *delta* if the writer is still current, else None.

    The owner (the REPL app or agent) stores ``_stream_writer_token``;
    a new turn's claim bumps it, so the stale producer's deltas are
    dropped at the fence.
    """
    if stream_writer_is_current(owner, token):
        return delta
    return None
