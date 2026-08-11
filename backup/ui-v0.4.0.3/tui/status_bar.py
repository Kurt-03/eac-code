"""Status bar (TUI redesign Phase A.4).

Compact single-line widget at the bottom of the App, replacing the
Textual ``Footer``. Four anchors: model · mode · context% · cost.
Pure-string renderer (no Textual dependency), so it's easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StatusBar:
    model: str
    mode: str
    context_pct: int | None
    cost_usd: float

    def render(self) -> str:
        parts: list[str] = []
        parts.append(self.model or "—")
        parts.append(self.mode or "—")
        if self.context_pct is not None:
            parts.append(f"{self.context_pct}%")
        else:
            parts.append("—")
        # Skip a trailing "$0.0000" to keep the bar quiet at start.
        if self.cost_usd > 0:
            parts.append(f"${self.cost_usd:.4f}")
        return " · ".join(parts)
