"""Flat-message renderer for the v0.4.0 TUI redesign (Phase A.3).

Replaces the old RichLog/CSS-Boxes markup with simple monospaced lines.
Returns plain strings (no Textual markup) so the Log can write them
directly. Status / colour hinting is intentionally minimal — a single
accent character (`›` for user, `▸` for tools, `‖` for the inline
permission prompt) is the only visual signal beyond indentation.
"""

from __future__ import annotations

_MAX_ARGS = 80


def render_message(role: str, content: str, *,
                   name: str | None = None,
                   args: dict | None = None) -> str:
    """One flat line for the given *role*.

    - user        → ``› {content}``
    - assistant   → ``{content}``
    - tool_call   → ``▸ {name} {args}``
    - tool_result → 4-space-indented *content*
    - reasoning   → ``[reasoning] {content}`` (indented)
    - error       → ``✗ {content}``
    - anything else → *content* verbatim
    """
    if role == "user":
        return f"› {content}"
    if role == "tool_call":
        n = name or "tool"
        summary = _args_summary(args or {})
        return f"▸ {n} {summary}".rstrip()
    if role == "tool_result":
        return _indent(content)
    if role == "reasoning":
        return _indent(f"[reasoning] {content}")
    if role == "error":
        return f"✗ {content}"
    return content


def render_permission_prompt(tool: str, args: dict,
                             diff: str | None = None) -> str:
    """Inline permission question (Phase B). Flat text, no box.

    v0.0.1: the diff lines are colored (red ``-``, green ``+``, cyan
    ``@@``, blue file headers) instead of being escaped plain. The
    toolkit arguments and the legend are still escaped (``[y]``/``[a]``
    etc. would otherwise be eaten as style tags by Rich — v0.5.3 bug).
    """
    lines = [f"‖ Allow {_escape(tool)}?"]
    for key, value in _args_summary_dict(args).items():
        lines.append(f"‖   {_escape(key)}: {_escape(value)}")
    if diff:
        for dline in diff.splitlines()[:30]:
            lines.append(f"‖   {_render_diff_line(dline)}")
    lines.append("‖")
    lines.append(
        "‖   " + _escape("[y] once    [s] session    [a] always    "
                         "[n] deny    [p] pause    [Esc] deny")
    )
    return "\n".join(lines)


def _render_diff_line(line: str) -> str:
    """Render a single diff line with the appropriate Rich markup.

    - file headers (``--- a/...``, ``+++ b/...``) → bold blue
    - hunk markers (``@@ -... +... @@``) → bold cyan
    - insertions (``+...``) → green
    - deletions (``-...``) → red
    - context lines (`` ...``) → dim
    - everything else → escaped plain
    """
    if line.startswith("---") or line.startswith("+++"):
        return f"[bold blue]{_escape(line)}[/bold blue]"
    if line.startswith("@@"):
        return f"[bold cyan]{_escape(line)}[/bold cyan]"
    if line.startswith("+"):
        return f"[green]{_escape(line)}[/green]"
    if line.startswith("-"):
        return f"[red]{_escape(line)}[/red]"
    if line.startswith(" "):
        return f"[dim]{_escape(line)}[/dim]"
    return _escape(line)


def _escape(text: str) -> str:
    """Escape Rich markup brackets (``[``/``]`` → ``\\[...]``)."""
    from rich.markup import escape as _rich_escape

    return _rich_escape(text)


def _args_summary(args: dict) -> str:
    """Single-line summary of *args*; capped to keep the prompt narrow."""
    parts = _args_summary_dict(args)
    if not parts:
        return ""
    head, *rest = list(parts.items())
    rendered = f"{head[0]}: {head[1]}"
    if rest:
        rendered += f" (+{len(rest)})"
    return rendered[:_MAX_ARGS]


def _args_summary_dict(args: dict) -> dict:
    """Trimmed copy of *args*: hide empty values, cap key strings."""
    out: dict = {}
    for key, value in args.items():
        if value in (None, "", [], {}):
            continue
        text = str(value)
        if len(text) > _MAX_ARGS:
            text = text[: _MAX_ARGS - 1] + "…"
        out[key] = text
    return out


def _indent(text: str) -> str:
    """4-space indent for tool_result / reasoning lines."""
    if not text:
        return ""
    pad = "    "
    return "\n".join(pad + line for line in text.splitlines())
