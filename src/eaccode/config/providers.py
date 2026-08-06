"""BYOK-Provider-Konfiguration (Task 1.2).

User bringt eigene API-Keys mit — gespeichert in providers.yaml mit
SecretStr (kein Key landet im Klartext in Logs/Pydantic-Dumps).
"""
from __future__ import annotations

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

# Provider mit nativem LiteLLM-Profil (bekommen ihr eigenes Prefix)
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
        """Provider-Konfiguration → Umgebungsvariablen für LiteLLM."""
        prefix = self.name.upper().replace("-", "_")
        env = {f"{prefix}_API_KEY": self.api_key.get_secret_value()}
        if self.base_url:
            env[f"{prefix}_API_BASE"] = self.base_url
        env.update({f"EACCODE_{k.upper()}": v for k, v in self.extra.items()})
        return env


def save_providers(providers: list[ProviderConfig], path: Path) -> None:
    data = [
        {
            "name": p.name,
            "api_key": p.api_key.get_secret_value(),
            "model": p.model,
            "base_url": p.base_url,
            **({"extra": p.extra} if p.extra else {}),
        }
        for p in providers
    ]
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


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
