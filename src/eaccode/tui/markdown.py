"""Mini markdown renderer for the transcript (Hermes-style).

Covers the subset that matters in agent conversations: fenced code
blocks, inline code, bold/italic, lists, headings, blockquotes, and
links. Renders to Textual markup strings with the theme colors —
code gets the muted/border treatment like Hermes' <Md>.
"""

from __future__ import annotations

import re

_BLOCK_SPLIT = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
_LIST = re.compile(r"^[-*]\s+(.*)$")
_NUM_LIST = re.compile(r"^(\d+)\.\s+(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _inline(text: str, color: str = "grey93") -> str:
    """Inline formatting: links, inline code, bold, italic."""
    text = _LINK.sub(r"[\1]([\2])", text)  # keep as-is; strip url
    text = _INLINE_CODE.sub(rf"[{color}]\1[/]", text)
    text = _BOLD.sub(rf"[bold {color}]\1[/]", text)
    text = _ITALIC.sub(rf"[italic {color}]\1[/]", text)
    return text


def render_markdown(text: str, *, code_color: str = "grey58",
                    text_color: str = "grey93") -> str:
    """Render *text* as Textual markup with Hermes-ish coloring.

    Fenced blocks get a muted body; headings get bold; lists/numbers get
    a leading bullet in the accent color. Returns markup-safe string.
    """
    parts: list[str] = []
    pos = 0
    for match in _BLOCK_SPLIT.finditer(text):
        if match.start() > pos:
            parts.append(_render_prose(text[pos:match.start()], text_color))
        parts.append(f"[{code_color}]{match.group(2).rstrip()}[/]")
        pos = match.end()
    if pos < len(text):
        parts.append(_render_prose(text[pos:], text_color))
    return "\n".join(p for p in parts if p)


def _render_prose(block: str, color: str) -> str:
    lines: list[str] = []
    for raw in block.splitlines():
        line = raw
        heading = _HEADING.match(line)
        if heading:
            lines.append(f"[bold {color}]{_inline(heading.group(2), color)}[/]")
            continue
        quote = _QUOTE.match(line)
        if quote:
            lines.append(f"[dim]│ {_inline(quote.group(1), color)}[/]")
            continue
        num = _NUM_LIST.match(line)
        if num:
            lines.append(f"[bold cyan]{num.group(1)}.[/] {_inline(num.group(2), color)}")
            continue
        item = _LIST.match(line)
        if item:
            lines.append(f"[cyan]●[/] {_inline(item.group(1), color)}")
            continue
        if not line.strip():
            lines.append("")
            continue
        lines.append(_inline(line, color))
    return "\n".join(lines)
