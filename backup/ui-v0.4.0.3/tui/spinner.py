"""ASCII spinner (TUI redesign Phase A.2).

Claude-Code-style: ``⠋⠙⠸⠴⠦⠧`` cycling at 100 ms. The widget writes
``sp.frame()`` once per tick; ``tick()`` advances the index. ``start()``
and ``stop()`` are no-ops in tests (the App drives them via set_interval).
"""

from __future__ import annotations

import threading

_FRAMES = "⠋⠙⠸⠴⠦⠧"


class Spinner:
    def __init__(self, interval: float = 0.1) -> None:
        self.interval = interval
        self._index = 0
        self._lock = threading.Lock()
        self._running = False

    def frame(self) -> str:
        with self._lock:
            return _FRAMES[self._index]

    def tick(self) -> None:
        with self._lock:
            self._index = (self._index + 1) % len(_FRAMES)

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running
