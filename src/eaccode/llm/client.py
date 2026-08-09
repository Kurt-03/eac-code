"""LiteLLM client — orchestration shell.

Unified interface: complete() (sync, with retry) and stream() (async).
The heavy lifting lives in two mixins, extracted for maintainability:

- ``_ResolveMixin`` (``llm/_resolve.py``): model resolution, message and
  tool-schema conversion, per-request credential kwargs.
- ``_StreamMixin`` (``llm/_stream.py``): thread-based streaming producer.

Provider-specific details (prefix, keys, base URLs) come from providers.yaml.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import litellm
from litellm import completion
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from eaccode.config.providers import load_providers
from eaccode.llm._resolve import _ResolveMixin
from eaccode.llm._stream import ReasoningDelta, StreamUsage, _StreamMixin
from eaccode.llm.errors import RetryPolicy, classify_api_error
from eaccode.llm.model_switch import FallbackChain
from eaccode.llm.models import Message, ToolCall

# Re-exported for back-compat (existing `from eaccode.llm.client import X`
# call sites must keep working after the split).
__all__ = [
    "CompletionRequest",
    "CompletionResponse",
    "LLMClient",
    "ReasoningDelta",
    "StreamUsage",
    "TokenUsage",
]


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


def _is_transient(exc: Exception) -> bool:
    """Only transient failures (429/5xx/timeout/unknown) are retried."""
    return classify_api_error(exc).policy == RetryPolicy.RETRY


class LLMClient(_ResolveMixin, _StreamMixin):
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
        # DI seam for the streaming producer (see _stream.py:_produce).
        # Kept as an instance attribute so tests can inject a fake without
        # touching litellm's module globals.
        self.completion_fn = completion

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


# Back-compat aliases: the mixin classes are implementation details; the
# public surface of this module stays identical to pre-split client.py.
# (ReasoningDelta/StreamUsage/TokenUsage defined above; nothing else to alias.)
