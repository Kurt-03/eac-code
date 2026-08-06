"""Globale Settings (Task 1.3).

Alle persistenten Einstellungen in einer Pydantic-Klasse —
geladen/gespeichert als eaccode.yaml (XDG-Config-Verzeichnis).
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class PermissionMode(str, Enum):
    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    PLAN = "plan"
    BYPASS_PERMISSIONS = "bypassPermissions"


class CuratorSettings(BaseModel):
    """Selbst-Wartung: stale Skills, Memory-Dedupe (wie Hermes curator)."""

    enabled: bool = True
    interval_hours: int = 24
    stale_after_days: int = 90


class Settings(BaseModel):
    default_provider: str = "anthropic"
    default_model: str | None = None  # fällt auf das Provider-Modell zurück
    permission_mode: PermissionMode = PermissionMode.DEFAULT
    max_turns: int = Field(default=50, ge=1, le=200)
    max_budget_usd: float | None = None
    effort: str = "medium"  # low | medium | high
    stream: bool = True
    theme: str = "auto"
    auto_compact: bool = True
    compact_threshold: float = Field(default=0.7, ge=0.1, le=0.95)
    show_reasoning: bool = True  # wie Hermes display.show_reasoning
    max_parallel_agents: int = Field(default=6, ge=1, le=64)  # harter Cap für den Worker-Pool
    save_sessions: bool = True
    ignore_rules: bool = False  # --ignore-rules: Projekt-Context + Memory überspringen
    curator: CuratorSettings = CuratorSettings()

    @classmethod
    def load(cls, path: Path) -> "Settings":
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(**data)

    def save(self, path: Path) -> None:
        path.write_text(
            yaml.safe_dump(self.model_dump(mode="json"), default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
