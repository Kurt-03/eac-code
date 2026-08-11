"""Flat layout descriptor (TUI redesign Phase A.1).

``TUILayout`` is a small value object the App composes: log + separator
+ input + status_bar. No boxes, no header/footer, single accent colour.
Keeping it as a dataclass (no Textual Widgets) means tests run without
a terminal and the layout can be reasoned about independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Palette:
    accent: str = "cyan"
    dim: str = "grey"
    muted: str = "grey50"


@dataclass
class TUILayout:
    regions: list[str] = field(default_factory=lambda: [
        "log", "separator", "input", "status_bar",
    ])
    has_header: bool = False
    has_footer: bool = False
    has_input_border: bool = False
    has_log_border: bool = False
    palette: Palette = field(default_factory=Palette)
    separator_char: str = "─"

    def separator(self, width: int) -> str:
        return self.separator_char * width
