"""Role glyphs (ported from Hermes ui-tui/src/domain/roles.ts).

Every transcript line carries a gutter glyph + body color per role:
user → the brand prompt (❯), assistant → the tool glyph (⚡), system →
a middot (·), tool → ⚡ in muted. The gutter is fixed-width so the
transcript reads as clean columns.
"""

from __future__ import annotations

from eaccode.tui.theme import Theme

GUTTER_WIDTH = 3


def role_style(role: str, theme: Theme) -> tuple[str, str]:
    """Return (glyph, color) for a transcript role."""
    c = theme.color
    if role == "user":
        return theme.brand.prompt, c.label
    if role == "assistant":
        return theme.brand.tool, c.text
    if role == "tool":
        return "⚡", c.muted
    if role == "event":
        return "◈", c.muted
    return "·", c.muted  # system


def gutter_line(glyph: str, color: str) -> str:
    """Render the gutter cell for one line (glyph right-aligned)."""
    return f"[{color}]{glyph:>{GUTTER_WIDTH}}[/]"
