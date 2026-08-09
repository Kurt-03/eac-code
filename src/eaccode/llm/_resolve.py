"""Model resolution + request conversion for the LLM client.

Extracted from ``client.py`` (god-file decomposition): everything that
maps eaccode's own request types onto LiteLLM's call shape lives here as
a mixin, so ``LLMClient`` stays a thin orchestration shell.

Provider-specific details (prefix, keys, base URLs) come from providers.yaml.
"""

from __future__ import annotations

import json

from eaccode.llm.models import Message


class _ResolveMixin:
    """Model resolution and LiteLLM message/tool conversion."""

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
        req,
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
