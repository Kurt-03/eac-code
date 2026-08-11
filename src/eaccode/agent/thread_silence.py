"""Thread-scoped silence (F.29) — background workers stay quiet.

Workers (session saves, background reviews) must not spam the REPL log.
The context manager marks a worker as silent; UI-facing code can query
``is_worker_silent()`` to decide whether to render. The review worker
still writes its three deliberate lines (the proposal IS the feature);
everything else stays silent.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

_state = threading.local()


@contextmanager
def thread_silenced():
    """Mark the current thread as a silent background worker."""
    previous = getattr(_state, "silent", False)
    _state.silent = True
    try:
        yield
    finally:
        _state.silent = previous


def is_worker_silent() -> bool:
    return bool(getattr(_state, "silent", False))
