"""Modell-Aliase + Fallback-Kette (Task 2.5, Hermes-Muster).

User-Aliase schlagen Built-ins; Fallback-Kette ersetzt Provider
bei Rate-Limits/Timeouts (wie `hermes fallback add`).
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from eaccode.config.providers import NATIVE_LITELLM_PROVIDERS


class AliasConfig(BaseModel):
    provider: str
    model: str
    base_url: str | None = None


@dataclass(frozen=True)
class ResolvedModel:
    provider: str
    model: str
    base_url: str | None = None

    @property
    def litellm_id(self) -> str:
        if self.provider in NATIVE_LITELLM_PROVIDERS:
            return f"{self.provider}/{self.model}"
        return f"openai/{self.model}"  # custom Endpoints


class ModelResolver:
    """User-Aliase (Settings.model_aliases) schlagen Built-ins."""

    BUILTINS: dict[str, ResolvedModel] = {
        "sonnet": ResolvedModel("anthropic", "claude-sonnet-4-6"),
        "opus": ResolvedModel("anthropic", "claude-opus-4-6"),
        "haiku": ResolvedModel("anthropic", "claude-haiku-4-5"),
        "gpt": ResolvedModel("openai", "gpt-4o"),
        "o3": ResolvedModel("openai", "o3"),
        "gemini": ResolvedModel("google", "gemini-2.5-pro"),
        "deepseek": ResolvedModel("deepseek", "deepseek-chat"),
        "minimax": ResolvedModel("minimax", "MiniMax-M2"),
    }

    def __init__(self, aliases: dict[str, AliasConfig] | None = None) -> None:
        self.aliases = aliases or {}

    def resolve(self, name: str) -> ResolvedModel:
        if name in self.aliases:  # 1. User-Alias zuerst
            a = self.aliases[name]
            return ResolvedModel(a.provider, a.model, a.base_url)
        if name in self.BUILTINS:  # 2. Built-in-Alias
            return self.BUILTINS[name]
        if "/" in name:  # 3. Vollqualifiziert "provider/model"
            provider, model = name.split("/", 1)
            return ResolvedModel(provider, model)
        raise ValueError(f"Unknown model alias: {name}")


class FallbackChain:
    """Ersatz-Provider in Reihenfolge — wie `hermes fallback add`."""

    def __init__(self, chain: list[tuple[str, str]] | None = None) -> None:
        self.chain = chain or []

    def next_after(self, index: int) -> tuple[str, str] | None:
        return self.chain[index + 1] if index + 1 < len(self.chain) else None
