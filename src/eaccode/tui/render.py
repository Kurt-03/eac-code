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

    v0.0.1: the header carries a tool-specific subtitle (path + bytes,
    command, replace hint) next to the "Allow <tool>?" call. The diff
    lines are colored (red ``-``, green ``+``, cyan ``@@``, blue file
    headers) instead of being escaped plain. The legend is still escaped
    (``[y]``/``[a]`` would otherwise be eaten as style tags by Rich).
    """
    subtitle = _format_tool_subtitle(tool, args)
    if subtitle:
        header = f"‖  [bold]Allow {_escape(tool)}?[/bold]  [dim]{_escape(subtitle)}[/dim]"
    else:
        header = f"‖  [bold]Allow {_escape(tool)}?[/bold]"
    lines = [header]
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


def _format_tool_subtitle(tool: str, args: dict) -> str:
    """One-line summary of the tool call, shown in the prompt header.

    - bash     → "command: <cmd>"
    - read     → "path"
    - write    → "path · N bytes"
    - edit     → "path · replace 'old' → 'new'"
    - everything else → first non-empty argument value
    """
    if tool == "bash":
        cmd = args.get("command", "")
        return f"{cmd}" if cmd else ""
    if tool == "read":
        path = args.get("path", "")
        return f"{path}" if path else ""
    if tool == "write":
        path = args.get("path", "")
        content = args.get("content", "")
        size = len(content) if isinstance(content, str) else 0
        if path and content:
            return f"{path} · {size} bytes"
        return f"{path}" if path else ""
    if tool == "edit":
        path = args.get("path", "")
        old = args.get("old_string", "")
        new = args.get("new_string", "")
        if path and old and new:
            return f"{path} · replace '{old}' → '{new}'"
        return f"{path}" if path else ""
    # Fallback: first non-empty value
    for v in args.values():
        if v not in (None, "", [], {}):
            return str(v)[:80]
    return ""


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
