"""Sync iterator front-end for AgentLoop.

The classic REPL (v0.7.2+) needs to iterate over agent events without
managing an asyncio loop of its own.

Architecture:

  - A worker thread runs ``asyncio.run`` with the LLM coroutines.
  - Events are forwarded to the REPL via a thread-safe ``queue.Queue``.
  - Permission asks are also events: the REPL receives a ``permission``
    event, reads from stdin in the main thread, and posts the answer
    back into a second queue (``resolve_queue``).
  - The worker thread polls the resolve queue on each tick and resolves
    the matching ``asyncio.Future`` via ``loop.call_soon_threadsafe``.

This keeps the main thread free for stdin (prompt_toolkit) and the
worker thread free for async LLM calls — no cross-thread await hazards.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from eaccode.permissions.prompts import PermissionChoice

EventKind = Literal[
    "text",        # payload={"delta": str}
    "reasoning",   # payload={"delta": str}
    "tool_call",   # payload={"id", "name", "arguments"}
    "tool_result", # payload={"id", "name", "content", "is_error"}
    "permission",  # payload={"id", "tool", "arguments", "question"}
    "usage",       # payload={"tokens_in", "tokens_out", "cost_usd"}
    "error",       # payload={"message": str}
    "done",        # payload={}
]


@dataclass(frozen=True)
class AgentEvent:
    kind: EventKind
    payload: dict = field(default_factory=dict)


@dataclass
class _PendingAsk:
    ask_id: int
    future: asyncio.Future
    event: AgentEvent


class _EventBus:
    """Two-way bridge between REPL main thread and asyncio worker thread."""

    def __init__(self) -> None:
        self.events: queue.Queue[AgentEvent | None] = queue.Queue()
        self.resolves: queue.Queue[tuple[int, PermissionChoice]] = queue.Queue()
        self.worker_ready = threading.Event()
        self.worker_failed: BaseException | None = None

    def put_event(self, event: AgentEvent) -> None:
        self.events.put(event)

    def put_sentinel(self) -> None:
        self.events.put(None)

    def get_resolve(self, timeout: float | None = None):
        return self.resolves.get(timeout=timeout)


def run_repl_sync(
    loop_obj: AgentLoop,
    messages: list,
    resolve_queue: queue.Queue | None = None,
) -> Iterator[AgentEvent]:
    """Yield AgentEvent records from an AgentLoop, one at a time.

    The REPL receives permission events and is expected to call
    ``resolve_permission(bus, ask_id, choice)`` from the main thread.
    When ``resolve_queue`` is given, it's used instead of the bus — the
    REPL just puts (ask_id, choice) tuples in.
    """
    bus = _EventBus()
    pending: dict[int, _PendingAsk] = {}
    if resolve_queue is not None:
        bus.resolves = resolve_queue  # REPL owns the queue
    # Else the runner creates its own bus.resolves internally.

    async def _driver() -> None:
        try:
            async def ask_async(tool: str, args: dict, question: str):
                """Future that the REPL resolves from the main thread."""
                fut: asyncio.Future[PermissionChoice] = (
                    asyncio.get_event_loop().create_future()
                )
                ask_id = max(pending.keys(), default=0) + 1
                pending[ask_id] = _PendingAsk(
                    ask_id=ask_id, future=fut,
                    event=AgentEvent("permission", {
                        "id": ask_id, "tool": tool,
                        "arguments": args, "question": question,
                    }),
                )
                bus.put_event(pending[ask_id].event)
                return await fut

            def on_text(delta: str) -> None:
                bus.put_event(AgentEvent("text", {"delta": delta}))

            def on_reasoning(delta: str) -> None:
                bus.put_event(AgentEvent("reasoning", {"delta": delta}))

            def on_tool_call(tc: Any) -> None:
                bus.put_event(AgentEvent("tool_call", {
                    "id": tc.id, "name": tc.name,
                    "arguments": tc.arguments,
                }))

            def on_tool_result(tc: Any, result: Any) -> None:
                bus.put_event(AgentEvent("tool_result", {
                    "id": tc.id, "name": tc.name,
                    "content": result.content or "",
                    "is_error": result.is_error,
                }))

            # Resolve poller — runs as a task on the worker loop.
            async def _resolve_poller() -> None:
                while True:
                    try:
                        ask_id, choice = await asyncio.get_event_loop().run_in_executor(
                            None, bus.get_resolve, 0.1,
                        )
                    except queue.Empty:
                        await asyncio.sleep(0.05)
                        continue
                    pending_ask = pending.pop(ask_id, None)
                    if pending_ask and not pending_ask.future.done():
                        pending_ask.future.set_result(choice)

            # Wire the ask callback into the agent.
            loop_obj.config.ask_async = ask_async  # type: ignore[assignment]
            poller_task = asyncio.create_task(_resolve_poller())

            try:
                await loop_obj.run_streaming(
                    messages,
                    on_text_delta=on_text,
                    on_reasoning_delta=on_reasoning,
                    on_tool_call=on_tool_call,
                    on_tool_result=on_tool_result,
                )
            finally:
                poller_task.cancel()
        except BaseException as e:
            bus.worker_failed = e
            bus.put_event(AgentEvent("error", {"message": str(e)}))
        finally:
            bus.put_sentinel()
            bus.worker_ready.set()

    thread = threading.Thread(
        target=lambda: asyncio.run(_driver()),
        name="eaccode-agent-driver",
        daemon=True,
    )
    thread.start()

    # The REPL's main thread consumes events here. When it sees a
    # permission event, it should call ``resolve_permission(bus, id, choice)``.
    try:
        while True:
            event = bus.events.get()
            if event is None:
                break
            yield event
    finally:
        # Make sure the worker thread can exit if the REPL drops out.
        bus.put_sentinel()
        thread.join(timeout=2.0)


def resolve_permission(
    bus: _EventBus, ask_id: int, choice: PermissionChoice,
) -> None:
    """Called from the REPL main thread to answer a permission ask."""
    bus.resolves.put((ask_id, choice))
