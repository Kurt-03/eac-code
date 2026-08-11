"""Theme (ported from Hermes ui-tui/src/theme.ts, adapted for eaccode).

The Hermes dark palette is a muted, low-saturation set: gold-ish muted
accents on a transparent terminal background. We keep the *shape* of
the Hermes ThemeColors/ThemeBrand but map them onto Textual's named
styles so the app works on any terminal (256-color or truecolor).

Color roles (Hermes semantics):
- muted  = secondary text (timeline, tool results, hints)
- accent = interactive highlights (completions, links)
- label  = user-message body color
- border = subtle separators
- ok/error/warn = status traffic lights
- tool   = tool-call markers (⚡/●)
- prompt = composer glyph (❯)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeColors:
    primary: str = "cyan"
    accent: str = "cyan"
    border: str = "grey37"
    text: str = "grey93"
    muted: str = "grey58"
    label: str = "grey87"
    ok: str = "green"
    error: str = "red"
    warn: str = "yellow"
    tool: str = "magenta"
    thinking: str = "grey50"
    prompt: str = "cyan"
    status_bg: str = "grey19"
    status_fg: str = "grey85"
    status_good: str = "green"
    status_warn: str = "yellow"
    status_bad: str = "red"


@dataclass(frozen=True)
class ThemeBrand:
    name: str = "eaccode"
    icon: str = "⚡"
    prompt: str = "❯"
    welcome: str = "Welcome to eaccode — autonomous coding agent."
    tool: str = "⚡"
    help_header: str = "Commands"


@dataclass(frozen=True)
class Theme:
    color: ThemeColors = ThemeColors()
    brand: ThemeBrand = ThemeBrand()


DEFAULT_THEME = Theme()
