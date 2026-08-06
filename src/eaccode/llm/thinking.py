"""Provider-specific thinking/reasoning (Task 2.4).

`effort: low|medium|high` is translated per provider+model into the right
API parameter. Reasoning works differently for every provider:

- Anthropic: thinking.budget_tokens (Sonnet/Opus only — not Haiku)
- OpenAI o-series: reasoning_effort (GPT-4o: none at all)
- Gemini: thinkingConfig.thinkingBudget
- DeepSeek/Qwen/R1/Ollama: NO parameter — reasoning_content arrives in the stream
- Unknown models: safe no-op, never crash
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
    """How a provider model accepts reasoning."""

    kind: str  # "budget" | "effort" | "stream" | "none"
    budgets: dict[EffortLevel, int] | None = None  # for kind="budget"
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
    "deepseek": ThinkingProfile("stream"),  # reasoning_content in the stream
    "ollama": ThinkingProfile("stream"),
}


class ThinkingMapper:
    """Translates EffortLevel → provider-specific request parameters."""

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
        return {}  # "stream" (automatic, rendering only) or "none"

    def _profile_for(self, model: str) -> ThinkingProfile:
        for key, profile in PROFILES.items():
            if model.startswith(key):
                return profile
        return ThinkingProfile("none")

    def supports_thinking(self, model: str) -> bool:
        return self._profile_for(model).kind != "none"

    def is_stream_reasoning(self, model: str) -> bool:
        """Models that deliver reasoning_content in the stream (DeepSeek/Qwen/R1)."""
        return self._profile_for(model).kind == "stream"
