"""v0.4.0 SuggestionOverlay (TUI redesign Phase C.1).

A flat list under the input that shows the current completions. The App
renders it as plain text lines (no border, no box) when slash/at-prefix
is active; hides it on Esc. Selection moves with arrow keys; Enter
executes the highlighted item.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SuggestionOverlay:
    items: list[tuple[str, str]] = None  # type: ignore
    index: int = 0
    max_visible: int = 8

    def __post_init__(self) -> None:
        if self.items is None:
            self.items = []

    def set_items(self, items: list[tuple[str, str]]) -> None:
        self.items = list(items)
        self.index = 0

    def current(self) -> tuple[str, str] | None:
        if not self.items:
            return None
        return self.items[self.index]

    def move(self, delta: int) -> None:
        if not self.items:
            return
        self.index = max(0, min(len(self.items) - 1, self.index + delta))

    def render_lines(self) -> list[str]:
        """Flat lines: `▸ /help  Show commands` for current, indented for rest."""
        if not self.items:
            return []
        out: list[str] = []
        visible = self.items[: self.max_visible]
        for i, (name, desc) in enumerate(visible):
            marker = "▸" if i == self.index else " "
            out.append(f"  {marker} {name:24s} {desc}")
        if len(self.items) > self.max_visible:
            out.append(f"  … (+{len(self.items) - self.max_visible} more)")
        return out
