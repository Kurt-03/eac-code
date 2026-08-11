"""BYOK provider configuration (Task 1.2).

Users bring their own API keys — stored in providers.yaml with
SecretStr (no key ever appears in plaintext in logs or Pydantic dumps).
"""
from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, SecretStr

ProviderName = Literal[
    "anthropic",
    "openai",
    "google",
    "ollama",
    "openrouter",
    "mistral",
    "groq",
    "xai",
    "deepseek",
    "minimax",
    "opencode-go",
]

# Providers with a native LiteLLM profile (get their own prefix)
NATIVE_LITELLM_PROVIDERS = {
    "anthropic",
    "openai",
    "google",
    "deepseek",
    "xai",
    "groq",
    "mistral",
    "minimax",
}


class ProviderConfig(BaseModel):
    name: ProviderName
    api_key: SecretStr
    model: str
    base_url: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)

    def to_env(self) -> dict[str, str]:
        """Provider config → environment variables for LiteLLM."""
        prefix = self.name.upper().replace("-", "_")
        env = {f"{prefix}_API_KEY": self.api_key.get_secret_value()}
        if self.base_url:
            env[f"{prefix}_API_BASE"] = self.base_url
        env.update({f"EACCODE_{k.upper()}": v for k, v in self.extra.items()})
        return env

    def litellm_model(self, model: str) -> str:
        """Model name → LiteLLM ID.

        Native profiles (minimax, anthropic, ...) get their own prefix;
        custom OpenAI-compatible endpoints (opencode-go, ...) get the `openai/` prefix.
        """
        if model.startswith(("openai/", "minimax/", "anthropic/", "google/", "deepseek/")):
            return model  # bereits prefixed
        if self.name in NATIVE_LITELLM_PROVIDERS:
            return f"{self.name}/{model}"
        return f"openai/{model}"  # custom/openai-kompatibel


def save_providers(providers: list[ProviderConfig], path: Path) -> None:
    data = [
        {
            "name": p.name,
            "api_key": p.api_key.get_secret_value(),
            "model": p.model,
            "base_url": p.base_url,
            **( {"extra": p.extra} if p.extra else {}),
        }
        for p in providers
    ]
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    # Keys are secrets: the file must never be world-readable, no matter
    # which code path saved it (P0.6 Bug 4 — centralize the chmod 600).
    with contextlib.suppress(OSError):
        path.chmod(0o600)


def load_providers(path: Path) -> list[ProviderConfig]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [
        ProviderConfig(
            name=p["name"],
            api_key=p["api_key"],
            model=p["model"],
            base_url=p.get("base_url"),
            extra=p.get("extra", {}),
        )
        for p in raw
    ]
