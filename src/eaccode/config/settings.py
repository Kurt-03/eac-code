"""Global settings (Task 1.3).

All persistent settings in one Pydantic class —
loaded/saved as eaccode.yaml (XDG config directory).
"""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PermissionMode(StrEnum):
    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    BYPASS_PERMISSIONS = "bypassPermissions"
    # B.3: `smart` was renamed — the honest name is safeAuto: bash is
    # classified by an aux LLM (with key-pattern fallback) and fails
    # open to manual approval; it never silently auto-allows.
    SAFE_AUTO = "safeAuto"


class CuratorSettings(BaseModel):
    """Self-maintenance: stale skills, memory dedupe (like Hermes curator)."""

    enabled: bool = True
    interval_hours: int = 24
    stale_after_days: int = 90


class SkillSettings(BaseModel):
    """A.7: skill loading configuration."""

    auto_load: bool = True  # inject skills into the system prompt
    dirs: list[str] = Field(
        default_factory=list,
        description="Extra skill directories (besides the default config dir)",
    )


class Settings(BaseModel):
    default_provider: str = "anthropic"
    default_model: str | None = None  # falls back to the provider's model
    permission_mode: PermissionMode = PermissionMode.DEFAULT
    max_turns: int = Field(default=50, ge=1, le=200)
    max_budget_usd: float | None = None
    effort: str = "medium"  # low | medium | high
    stream: bool = True
    theme: str = "auto"
    auto_compact: bool = True
    compact_threshold: float = Field(default=0.7, ge=0.1, le=0.95)
    show_reasoning: bool = True  # wie Hermes display.show_reasoning
    max_parallel_agents: int = Field(default=6, ge=1, le=64)  # hard cap for the worker pool
    save_sessions: bool = True
    ignore_rules: bool = False  # --ignore-rules: skip project context + memory
    hooks_enabled: bool = True  # P0.10: run hooks from config_dir/hooks/
    memory_nudge_every_turns: int = Field(
        default=5, ge=0,
        description="A.9: hint to save memory every N turns (0 = off)",
    )
    review_every_turns: int = Field(
        default=5, ge=0,
        description="C.1: background review every N turns (0 = off)",
    )
    skills: SkillSettings = SkillSettings()
    curator: CuratorSettings = CuratorSettings()

    @classmethod
    def load(cls, path: Path) -> Settings:
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        # B.3/E.4: migrate the renamed permission mode.
        if data.get("permission_mode") == "smart":
            data["permission_mode"] = PermissionMode.SAFE_AUTO.value
        return cls(**data)

    def save(self, path: Path) -> None:
        path.write_text(
            yaml.safe_dump(
                self.model_dump(mode="json"), default_flow_style=False, allow_unicode=True
            ),
            encoding="utf-8",
        )
