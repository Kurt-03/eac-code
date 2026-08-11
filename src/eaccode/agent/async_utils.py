"""Async utilities (F.14) — small helpers for the event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


def cancel_async_task(task: Any) -> None:
    """Cancel a task safely (no-op for None/done tasks)."""
    if task is None or task.done():
        return
    task.cancel()


async def race_with_timeout(coro: Awaitable, timeout: float) -> Any:
    """Await *coro* with a hard timeout; raises asyncio.TimeoutError."""
    return await asyncio.wait_for(coro, timeout=timeout)


async def run_sync_in_thread(fn: Callable, *args, **kwargs) -> Any:
    """Run a blocking callable in the default executor."""
    return await asyncio.to_thread(fn, *args, **kwargs)
