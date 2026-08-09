"""Streaming producer for the LLM client.

Extracted from ``client.py`` (god-file decomposition). litellm's
streaming is synchronous — iterating its generator inside the event loop
would freeze the UI for seconds per chunk. The sync iteration therefore
runs in a worker thread; parsed chunks arrive through an asyncio.Queue,
so the UI stays live while tokens flow.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from eaccode.llm.models import ToolCall


class ReasoningDelta:
    """reasoning_content from the stream (DeepSeek/Qwen/R1) —
    delivered separately from the answer text."""

    def __init__(self, text: str) -> None:
        self.text = text


class StreamUsage:
    """Usage reported at the end of a stream (OpenAI-compatible)."""

    def __init__(self, input_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost_usd = cost_usd


class _StreamMixin:
    """Streaming request handling (producer thread + queue)."""

    async def stream(
        self, req
    ) -> AsyncIterator[str | ToolCall | ReasoningDelta | StreamUsage]:
        """Yields text deltas, reasoning deltas, usage, and finally the
        tool calls."""
        kwargs = self._base_kwargs(req)
        if req.temperature is not None:
            kwargs["temperature"] = req.temperature

        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        loop = asyncio.get_running_loop()

        def _put(item) -> None:
            # asyncio.Queue is not thread-safe: put_nowait from a worker
            # thread would never wake the consumer. call_soon_threadsafe is
            # the canonical way to hand items into the loop from a thread.
            loop.call_soon_threadsafe(queue.put_nowait, item)

        def _field(obj, name: str, default=None):
            """Read a field from either a pydantic object or a plain dict.

            litellm versions differ: ModelResponse.model_validate produces
            dict deltas in some releases, pydantic objects in others.
            """
            if isinstance(obj, dict):
                return obj.get(name, default)
            return getattr(obj, name, default)

        def _produce() -> None:
            """Sync producer: call litellm, parse chunks, queue objects."""
            # completion_fn is the DI seam: set in LLMClient.__init__ to
            # litellm.completion; tests monkeypatch
            # `eaccode.llm.client.completion` and the client picks it up
            # at construction time (back-compat with pre-split tests).
            completion_fn = self.completion_fn
            try:
                response = completion_fn(**kwargs)  # stream=True via req.stream
            except Exception as e:  # deliver errors to the consumer
                _put(e)
                return
            tool_buf: dict[int, dict] = {}
            usage = None
            for chunk in response:
                choices = _field(chunk, "choices") or []
                if not choices:
                    # final chunk carries usage (OpenAI-compatible streams)
                    u = _field(chunk, "usage")
                    if u and (_field(u, "prompt_tokens") or _field(u, "completion_tokens")):
                        usage = StreamUsage(
                            input_tokens=_field(u, "prompt_tokens") or 0,
                            output_tokens=_field(u, "completion_tokens") or 0,
                        )
                    continue
                delta = _field(choices[0], "delta") or {}
                reasoning = _field(delta, "reasoning_content")
                if reasoning:
                    _put(ReasoningDelta(reasoning))
                content = _field(delta, "content")
                if content:
                    _put(content)
                for tc in _field(delta, "tool_calls") or []:
                    buf = tool_buf.setdefault(
                        _field(tc, "index") or 0,
                        {
                            "id": _field(tc, "id") or "",
                            "name": _field(_field(tc, "function"), "name") or "",
                            "args": "",
                        },
                    )
                    args = _field(_field(tc, "function"), "arguments")
                    if args:
                        buf["args"] += args
            for buf in tool_buf.values():
                try:
                    args = json.loads(buf["args"]) if buf["args"] else {}
                except (json.JSONDecodeError, TypeError):
                    args = {}
                _put(ToolCall(id=buf["id"], name=buf["name"], arguments=args))
            if usage:
                _put(usage)
            _put(None)

        producer = asyncio.create_task(asyncio.to_thread(_produce))
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            await producer
