"""Mini markdown renderer for the transcript (Hermes-style).

Covers the subset that matters in agent conversations: fenced code
blocks (with language tag, tolerant of OPEN fences while streaming),
inline code, bold/italic, lists, headings, blockquotes, and links.
All user/model text is Rich-markup-escaped before styling — the
transcript Log runs with markup=True and would otherwise eat bracket
content like ``arr[i]`` (B3/B4 audit fixes).
"""

from __future__ import annotations

import re

# Warm accent for code (Hermes' syntaxString role is a gold-ish tone).
_CODE_COLOR = "#dca050"
_BLOCK_COLOR = "grey74"
_TEXT_COLOR = "grey93"

_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
_LIST = re.compile(r"^[-*]\s+(.*)$")
_NUM_LIST = re.compile(r"^(\d+)\.\s+(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _escape(text: str) -> str:
    """Rich-markup-escape arbitrary text (brackets must survive)."""
    from rich.markup import escape as _rich_escape

    return _rich_escape(text)


def _inline(text: str, color: str = _TEXT_COLOR) -> str:
    """Inline formatting on ALREADY-ESCAPED *text*: links, code, bold,
    italic. Order matters: escape first, then wrap fragments in our
    own tags (which are intentionally NOT escaped)."""
    # B4 (audit): links render as their label only — the old regex
    # produced `[label]([url])` which the markup parser ate completely.
    text = _LINK.sub(lambda m: f"[{m.group(1)}]", text)
    text = _INLINE_CODE.sub(rf"[bold {_CODE_COLOR}]\1[/]", text)
    text = _BOLD.sub(rf"[bold {color}]\1[/]", text)
    text = _ITALIC.sub(rf"[italic {color}]\1[/]", text)
    return text


def render_markdown(text: str, *, code_color: str = _CODE_COLOR,
                    text_color: str = _TEXT_COLOR) -> str:
    """Render *text* as Textual markup.

    Line-based parser: fenced blocks (```lang … ```) get the language
    tag and a muted body; an UNCLOSED fence (mid-stream, B7 audit)
    renders the remaining lines as code instead of jumping to prose.
    """
    lines = text.splitlines()
    out: list[str] = []
    in_code = False
    code_lang = ""
    code_lines: list[str] = []

    def flush_code() -> None:
        nonlocal code_lines
        if code_lines:
            lang = f"[bold {code_color}]{_escape(code_lang)}[/] " \
                if code_lang else ""
            body = "\n".join(
                f"[{_BLOCK_COLOR}]{_escape(line_)}[/]" for line_ in code_lines
            )
            out.append(f"{lang}{body}")
        code_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                in_code = False
                flush_code()
            else:
                if code_lines:  # dangling prose before the fence
                    out.append(_render_prose(code_lines, text_color))
                    code_lines = []
                in_code = True
                code_lang = stripped[3:].strip()
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        # prose line — accumulate until the next fence so blocks render
        # as a unit
        if code_lines:
            out.append(_render_prose(code_lines, text_color))
            code_lines = []
        code_lines = [line]
        i += 1
    if in_code:
        # B7 (audit): unclosed fence (streaming) — render as code.
        flush_code()
    elif code_lines:
        out.append(_render_prose(code_lines, text_color))
    return "\n".join(p for p in out if p)


def _render_prose(block: list[str], color: str) -> str:
    lines: list[str] = []
    for raw in block:
        line = raw
        heading = _HEADING.match(line)
        if heading:
            lines.append(
                f"[bold {color}]{_inline(_escape(heading.group(2)), color)}[/]"
            )
            continue
        quote = _QUOTE.match(line)
        if quote:
            lines.append(
                f"[dim]│ {_inline(_escape(quote.group(1)), color)}[/]"
            )
            continue
        num = _NUM_LIST.match(line)
        if num:
            lines.append(
                f"[bold {_CODE_COLOR}]{num.group(1)}.[/] "
                f"{_inline(_escape(num.group(2)), color)}"
            )
            continue
        item = _LIST.match(line)
        if item:
            lines.append(
                f"[{_CODE_COLOR}]●[/] {_inline(_escape(item.group(1)), color)}"
            )
            continue
        if not line.strip():
            lines.append("")
            continue
        lines.append(_inline(_escape(line), color))
    return "\n".join(lines)
