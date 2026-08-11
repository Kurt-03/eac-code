"""Heartbeat (G.7) — periodic liveness signal for long-running work.

The REPL spinner already signals agent activity; this covers the tool
level: a long bash call can emit heartbeats so the UI can show the
process is alive instead of frozen.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from eaccode.agent.thread_silence import is_worker_silent


class Heartbeat:
    def __init__(self, interval: float, callback: Callable[[], None]) -> None:
        self.interval = max(0.1, interval)
        self.callback = callback
        self._task: Any = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.interval)
            try:
                if not is_worker_silent():  # F.29: quiet workers stay quiet
                    self.callback()
            except Exception:
                pass

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
