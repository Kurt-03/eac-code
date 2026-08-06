"""LiteLLM client (Task 2.2).

Unified interface: complete() (sync, with retry) and stream() (async).
Provider-specific details (prefix, keys, base URLs) come from providers.yaml.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

import litellm
from litellm import completion
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from eaccode.config.providers import load_providers
from eaccode.llm.models import Message, ToolCall


class ReasoningDelta:
    """reasoning_content from the stream (DeepSeek/Qwen/R1) — delivered separately from the answer text."""

    def __init__(self, text: str) -> None:
        self.text = text


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def __iadd__(self, other: "TokenUsage") -> "TokenUsage":
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
    ) -> None:
        self.default_model = default_model
        self.provider_name = provider_name
        self.effort = effort
        self.providers = {p.name: p for p in load_providers(providers_file)}
        for p in self.providers.values():
            for k, v in p.to_env().items():
                os.environ.setdefault(k, v)
        litellm.telemetry = False
        litellm.drop_params = True  # silently ignore unknown params (e.g. thinking)

    # ------------------------------------------------------------- Auflösung

    def _resolve_model(self, model: str | None) -> str:
        """Model name → LiteLLM ID (respecting the provider prefix)."""
        model = model or self.default_model
        if "/" in model:
            return model  # already qualified
        if self.provider_name:
            provider = self.providers.get(self.provider_name)
            if provider:
                return provider.litellm_model(model)
            return f"{self.provider_name}/{model}"
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

    def _base_kwargs(self, req: CompletionRequest) -> dict:
        kwargs = {
            "model": self._resolve_model(req.model),
            "messages": self._to_litellm_messages(req.messages, req.system),
            "max_tokens": req.max_tokens,
            "stream": req.stream,
        }
        # Pass credentials explicitly: LiteLLM only knows OPENAI_API_KEY for
        # `openai/`-prefixed custom endpoints, so per-request api_key/api_base
        # is required for BYOK providers like opencode-go (Task 1.5 finding).
        provider = self.providers.get(self.provider_name) if self.provider_name else None
        if provider:
            kwargs["api_key"] = provider.api_key.get_secret_value()
            if provider.base_url:
                kwargs["api_base"] = provider.base_url
        return kwargs

    # ------------------------------------------------------------- complete

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type(_RETRYABLE),
    )
    def complete(self, req: CompletionRequest) -> CompletionResponse:
        kwargs = self._base_kwargs(req)
        if req.tools:
            kwargs["tools"] = req.tools
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

    async def stream(self, req: CompletionRequest) -> AsyncIterator[str | ToolCall | ReasoningDelta]:
        """Yields text deltas, reasoning deltas, and finally the tool calls."""
        kwargs = self._base_kwargs(req)
        if req.tools:
            kwargs["tools"] = req.tools
        if req.temperature is not None:
            kwargs["temperature"] = req.temperature

        response = completion(**kwargs)  # litellm stream=True über req.stream
        tool_buf: dict[int, dict] = {}
        for chunk in response:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = choices[0].delta
            # reasoning_content (DeepSeek/Qwen/R1) — deliver separately
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield ReasoningDelta(reasoning)
                continue
            if delta.content:
                yield delta.content
            if getattr(delta, "tool_calls", None):
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_buf:
                        tool_buf[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_buf[idx]["id"] = tc.id
                    if tc.function.name:
                        tool_buf[idx]["name"] = tc.function.name
                    if tc.function.arguments:
                        tool_buf[idx]["arguments"] += tc.function.arguments
        for tc in tool_buf.values():
            try:
                args = json.loads(tc["arguments"])
            except (json.JSONDecodeError, TypeError):
                args = {}
            yield ToolCall(id=tc["id"], name=tc["name"], arguments=args)
