"""Status rule (ported from Hermes ui-tui/src/components/appChrome.tsx).

One terminal line under the composer:

    ─ ⠋ │ model │ 12k/200k tok [====----] 42% │ session-title

Left-pinned essentials: busy indicator, model, context. Right side:
session title or cwd. Segments yield progressively on narrow widths;
nothing truncates mid-segment. Pure string logic — easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass

SEP = " │ "


@dataclass
class StatusRule:
    busy: bool = False
    indicator: str = ""          # spinner frame or ✓
    verb: str = ""               # "working…" / "idle"
    model: str = ""
    branch: str = ""             # v0.0.1: current git branch (or "")
    context_used: int | None = None
    context_max: int | None = None
    cost_usd: float = 0.0
    right_label: str = ""        # session title or cwd
    session_started: bool = False

    def render(self, cols: int = 120) -> str:
        left = ["─" if not self.busy else self.indicator or "⠋"]
        left.append(self.verb or ("working…" if self.busy else "idle"))
        left.append(self.model or "—")
        if self.branch:
            left.append(self.branch)
        ctx = self._context_label()
        if ctx:
            left.append(ctx)
        if self.cost_usd > 0:
            left.append(f"${self.cost_usd:.4f}")
        essentials = SEP.join(left)
        right = self.right_label.strip()
        # Progressive disclosure: drop the right label first, then cost.
        if right and len(essentials) + len(SEP) + len(right) > cols:
            right = ""
        if right:
            return essentials + SEP + right
        return essentials

    def _context_label(self) -> str:
        if self.context_max and self.context_used is not None:
            return (f"{self._k(self.context_used)}/"
                    f"{self._k(self.context_max)} tok "
                    f"{self._bar()} {self._pct()}%")
        if self.context_used:
            return f"{self._k(self.context_used)} tok"
        return ""

    @staticmethod
    def _k(n: int) -> str:
        if n >= 1000:
            return f"{n / 1000:.0f}k"
        return str(n)

    def _pct(self) -> int:
        if not self.context_max:
            return 0
        used = self.context_used or 0
        return min(100, round(used * 100 / self.context_max))

    def _bar(self) -> str:
        if not self.context_max:
            return ""
        pct = self._pct()
        filled = max(0, min(10, round(pct / 10)))
        return "█" * filled + "░" * (10 - filled)
