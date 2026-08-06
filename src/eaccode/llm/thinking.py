"""Provider-spezifisches Thinking/Reasoning (Task 2.4).

`effort: low|medium|high` wird pro Provider+Modell in den richtigen
API-Parameter übersetzt. Reasoning funktioniert bei jedem Anbieter anders:

- Anthropic: thinking.budget_tokens (nur Sonnet/Opus — Haiku nicht)
- OpenAI o-Serie: reasoning_effort (GPT-4o: gar keiner)
- Gemini: thinkingConfig.thinkingBudget
- DeepSeek/Qwen/R1/Ollama: KEIN Parameter — reasoning_content kommt im Stream
- Unbekannte Modelle: safe no-op, nie crashen
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EffortLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ThinkingProfile:
    """Wie ein Provider-Modell Reasoning akzeptiert."""

    kind: str  # "budget" | "effort" | "stream" | "none"
    budgets: dict[EffortLevel, int] | None = None  # für kind="budget"
    budget_key: str | None = None  # "budget_tokens" | "thinkingBudget"


PROFILES: dict[str, ThinkingProfile] = {
    "anthropic/claude-sonnet": ThinkingProfile(
        "budget",
        {EffortLevel.LOW: 1024, EffortLevel.MEDIUM: 4096, EffortLevel.HIGH: 16384},
        "budget_tokens",
    ),
    "anthropic/claude-opus": ThinkingProfile(
        "budget",
        {EffortLevel.LOW: 2048, EffortLevel.MEDIUM: 8192, EffortLevel.HIGH: 32768},
        "budget_tokens",
    ),
    "anthropic/claude-haiku": ThinkingProfile("none"),
    "openai/o": ThinkingProfile("effort"),  # o1/o3/o4-mini → reasoning_effort
    "google/gemini-2.5": ThinkingProfile(
        "budget",
        {EffortLevel.LOW: 256, EffortLevel.MEDIUM: 1024, EffortLevel.HIGH: 8192},
        "thinkingBudget",
    ),
    "xai/grok": ThinkingProfile("effort"),
    "deepseek": ThinkingProfile("stream"),  # reasoning_content im Stream
    "ollama": ThinkingProfile("stream"),
}


class ThinkingMapper:
    """Übersetzt EffortLevel → provider-spezifische Request-Parameter."""

    def apply(self, model: str, effort: EffortLevel) -> dict:
        profile = self._profile_for(model)
        if profile.kind == "budget" and profile.budgets and profile.budget_key:
            budget = profile.budgets.get(effort)
            if budget:
                if "gemini" in model:
                    return {"thinkingConfig": {"thinkingBudget": budget}}
                return {"thinking": {"type": "enabled", "budget_tokens": budget}}
        if profile.kind == "effort":
            return {"reasoning_effort": effort.value}
        return {}  # "stream" (automatisch, nur Rendering) oder "none"

    def _profile_for(self, model: str) -> ThinkingProfile:
        for key, profile in PROFILES.items():
            if model.startswith(key):
                return profile
        return ThinkingProfile("none")

    def supports_thinking(self, model: str) -> bool:
        return self._profile_for(model).kind != "none"

    def is_stream_reasoning(self, model: str) -> bool:
        """Modelle, die reasoning_content im Stream liefern (DeepSeek/Qwen/R1)."""
        return self._profile_for(model).kind == "stream"
