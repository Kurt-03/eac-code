"""LiteLLM client (Task 2.2).

Unified interface: complete() (sync, with retry) and stream() (async).
Provider-specific details (prefix, keys, base URLs) come from providers.yaml.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import litellm
from litellm import completion
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from eaccode.config.providers import load_providers
from eaccode.llm.errors import RetryPolicy, classify_api_error
from eaccode.llm.model_switch import FallbackChain
from eaccode.llm.models import Message, ToolCall


def _is_transient(exc: Exception) -> bool:
    """Only transient failures (429/5xx/timeout/unknown) are retried."""
    return classify_api_error(exc).policy == RetryPolicy.RETRY


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


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def __iadd__(self, other: TokenUsage) -> TokenUsage:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cost_usd += other.cost_usd
        return self


@dataclass
class CompletionResponse:
    text: str
    tool_calls: list[ToolCall]
    stop_reason: str
    usage: TokenUsage
    model: str


@dataclass
class CompletionRequest:
    messages: list[Message]
    model: str | None = None
    tools: list[dict] | None = None
    max_tokens: int = 4096
    temperature: float | None = None
    system: str | None = None
    stream: bool = False


_RETRYABLE = (
    litellm.RateLimitError,
    litellm.Timeout,
    litellm.ServiceUnavailableError,
    litellm.InternalServerError,
)


class LLMClient:
    def __init__(
        self,
        default_model: str,
        providers_file: Path,
        provider_name: str | None = None,
        effort: str = "medium",
        fallback_chain: FallbackChain | None = None,
    ) -> None:
        self.default_model = default_model
        self.provider_name = provider_name
        self.effort = effort
        self.fallback_chain = fallback_chain or FallbackChain()
        self.providers = {p.name: p for p in load_providers(providers_file)}
        for p in self.providers.values():
            for k, v in p.to_env().items():
                os.environ.setdefault(k, v)
        litellm.telemetry = False
        litellm.drop_params = True  # silently ignore unknown params (e.g. thinking)

    # ------------------------------------------------------------- Auflösung

    def _resolve_model(
        self, model: str | None, provider_name: str | None = None
    ) -> str:
        """Model name → LiteLLM ID (respecting the provider prefix)."""
        model = model or self.default_model
        provider_name = provider_name or self.provider_name
        if "/" in model:
            return model  # already qualified
        if provider_name:
            provider = self.providers.get(provider_name)
            if provider:
                return provider.litellm_model(model)
            return f"{provider_name}/{model}"
        return model

    # ------------------------------------------------------- Konvertierung

    def _to_litellm_messages(
        self, messages: list[Message], system: str | None
    ) -> list[dict]:
        out: list[dict] = []
        if system:
            out.append({"role": "system", "content": system})
        for m in messages:
            if m.role.value == "system":
                out.append({"role": "system", "content": m.content[0].text})
            elif m.role.value == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.tool_call_id,
                        "content": m.content[0].text,
                    }
                )
            elif m.tool_calls:
                out.append(
                    {
                        "role": "assistant",
                        "content": "".join(
                            b.text for b in m.content if b.type == "text"
                        ),
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in m.tool_calls
                        ],
                    }
                )
            else:
                content: list[dict] = []
                for b in m.content:
                    if b.type == "text":
                        content.append({"type": "text", "text": b.text})
                    else:
                        content.append(
                            {"type": "image_url", "image_url": {"url": b.source.get("data", "")}}
                        )
                out.append({"role": m.role.value, "content": content})
        return out

    def _base_kwargs(
        self,
        req: CompletionRequest,
        *,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> dict:
        provider_name = provider_name or self.provider_name
        kwargs = {
            "model": self._resolve_model(model or req.model, provider_name),
            "messages": self._to_litellm_messages(req.messages, req.system),
            "max_tokens": req.max_tokens,
            "stream": req.stream,
        }
        if req.tools:
            kwargs["tools"] = self._to_litellm_tools(req.tools)
        # Pass credentials explicitly: LiteLLM only knows OPENAI_API_KEY for
        # `openai/`-prefixed custom endpoints, so per-request api_key/api_base
        # is required for BYOK providers like opencode-go (Task 1.5 finding).
        provider = self.providers.get(provider_name) if provider_name else None
        if provider:
            kwargs["api_key"] = provider.api_key.get_secret_value()
            if provider.base_url:
                kwargs["api_base"] = provider.base_url
        return kwargs

    @staticmethod
    def _to_litellm_tools(schemas: list[dict]) -> list[dict]:
        """Convert our Anthropic-style tool schemas to the OpenAI format.

        LiteLLM converts OpenAI → Anthropic automatically, but NOT the other
        way around — MiniMax rejected Anthropic-style tools with
        'invalid tool type' (2013) (live finding).
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object"}),
                },
            }
            for t in schemas
        ]

    # ------------------------------------------------------------- complete

    def complete(self, req: CompletionRequest) -> CompletionResponse:
        """Complete with retries, then walk the fallback chain (Task 2.5).

        Error policy (Phase A.4): 400/402 stop immediately (retry can't
        fix them), 401/403 skip retries and go straight to the fallback
        provider, 429/5xx/timeouts are retried with backoff, then fallback.
        """

        try:
            return self._complete_with_retry(req)
        except Exception as e:
            classified = classify_api_error(e)
            if classified.policy == RetryPolicy.STOP:
                raise  # budget/schema errors are permanent
            if not self.fallback_chain.chain:
                raise
            # auth errors (401/403) skip the retry loop — they already
            # bypassed it via _is_transient; retries only ran for transient
            for index in range(len(self.fallback_chain.chain)):
                provider_name, model = self.fallback_chain.chain[index]
                try:
                    return self._complete_with_retry(req, provider_name, model)
                except Exception as fb_e:
                    if classify_api_error(fb_e).policy == RetryPolicy.STOP:
                        raise
                    continue
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception(_is_transient),
        reraise=True,  # raise the original exception, not tenacity.RetryError
    )
    def _complete_with_retry(
        self,
        req: CompletionRequest,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> CompletionResponse:
        kwargs = self._base_kwargs(req, provider_name=provider_name, model=model)
        if req.temperature is not None:
            kwargs["temperature"] = req.temperature
        resp = completion(**kwargs)
        choice = resp.choices[0]
        msg = choice.message
        tool_calls: list[ToolCall] = []
        if getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, arguments=args)
                )
        usage = TokenUsage(
            input_tokens=getattr(resp.usage, "prompt_tokens", 0),
            output_tokens=getattr(resp.usage, "completion_tokens", 0),
            cost_usd=getattr(resp.usage, "cost", 0.0) or 0.0,
        )
        # normalize finish_reason: "tool_calls" (OpenAI) → "tool_use" (Anthropic convention)
        stop_reason = getattr(choice, "finish_reason", None) or "stop"
        if stop_reason == "tool_calls":
            stop_reason = "tool_use"
        return CompletionResponse(
            text=getattr(msg, "content", "") or "",
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
            model=getattr(resp, "model", kwargs["model"]),
        )

    # -------------------------------------------------------------- stream

    async def stream(
        self, req: CompletionRequest
    ) -> AsyncIterator[str | ToolCall | ReasoningDelta]:
        """Yields text deltas, reasoning deltas, and finally the tool calls.

        litellm's streaming is synchronous — iterating its generator inside
        the event loop would freeze the UI for seconds per chunk. The sync
        iteration therefore runs in a worker thread; parsed chunks arrive
        through an asyncio.Queue, so the UI stays live while tokens flow.
        """
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
            try:
                response = completion(**kwargs)  # stream=True via req.stream
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
