"""Slash-command overlay (Hermes-style menu over the composer).

When the user types ``/`` the app shows a ranked menu of matching
commands (fuzzy score, see fuzzy.py) directly above the input line —
no box, just lines with the cursor marker on the current entry.
Arrow keys move the cursor; Tab completes; Enter runs; Esc closes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from eaccode.tui.fuzzy import rank_slash_items
from eaccode.ui.command_def import COMMAND_REGISTRY


@dataclass
class SlashOverlay:
    query: str = ""
    items: list[dict] = field(default_factory=list)
    index: int = 0
    max_visible: int = 8

    def update(self, query: str) -> None:
        self.query = query
        if query.startswith("/"):
            raw = [
                {"name": cmd.name, "description": cmd.description,
                 "aliases": list(cmd.aliases)}
                for cmd in COMMAND_REGISTRY
            ]
            self.items = rank_slash_items(raw, query[1:])
        else:
            self.items = []
        self.index = 0

    def current(self) -> dict | None:
        if not self.items:
            return None
        return self.items[self.index]

    def move(self, delta: int) -> None:
        if not self.items:
            return
        self.index = max(0, min(len(self.items) - 1, self.index + delta))

    def visible(self) -> list[dict]:
        return self.items[: self.max_visible]

    def render_lines(self) -> list[str]:
        if not self.items:
            return []
        lines = []
        for i, item in enumerate(self.visible()):
            marker = "▸" if i == self.index else " "
            name = item["name"]
            desc = item.get("description", "")
            lines.append(f"  {marker} /{name:<20s} {desc[:60]}")
        if len(self.items) > self.max_visible:
            lines.append(f"  … (+{len(self.items) - self.max_visible} more)")
        return lines
