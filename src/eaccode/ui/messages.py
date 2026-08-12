"""System message rendering — plain-stdout variants for the classic REPL.

The original Rich-markup helpers stay for any caller that still feeds
them through a markup-aware log; the new ``plain_*`` helpers produce
ANSI-free lines that work in every terminal (including ones where the
user pipes ``eaccode`` into a file).
"""

from __future__ import annotations


def write_info(text: str) -> str:
    """Rich-markup variant — kept for callers that feed a Log widget."""
    return f"[dim][ i ] {text}[/dim]"


def write_warn(text: str) -> str:
    return f"[yellow][ ! ] {text}[/yellow]"


def write_error(text: str) -> str:
    return f"[red][ ✗ ] {text}[/red]"


# Plain-stdout variants for the classic REPL (v0.7.2+).

def plain_info(text: str) -> str:
    return f"[ i ] {text}"


def plain_warn(text: str) -> str:
    return f"[ ! ] {text}"


def plain_error(text: str) -> str:
    return f"[ X ] {text}"


def render_event_plain(event) -> str:
    """Format an AgentEvent as a single plain-text line for stdout.

    Token deltas (text/reasoning) are intentionally NOT rendered here —
    they need inline streaming (no trailing newline). The REPL loop
    handles them itself.
    """
    if event.kind == "tool_call":
        name = event.payload.get("name", "?")
        args = event.payload.get("arguments", {})
        # Compact one-line summary, args dumped after the name.
        arg_str = " ".join(f"{k}={v!r}" for k, v in args.items())
        return f"▸ {name} {arg_str}".rstrip()
    if event.kind == "tool_result":
        name = event.payload.get("name", "?")
        content = (event.payload.get("content") or "").strip()
        mark = "✗" if event.payload.get("is_error") else "✓"
        first_line = content.splitlines()[0] if content else ""
        preview = f"  {first_line[:120]}" if first_line else ""
        return f"  {mark} {name}{preview}"
    if event.kind == "usage":
        ti = event.payload.get("tokens_in", 0)
        to = event.payload.get("tokens_out", 0)
        cost = event.payload.get("cost_usd", 0.0)
        return f"[ i ] tokens in={ti} out={to} cost=${cost:.4f}"
    if event.kind == "error":
        return plain_error(event.payload.get("message", "unknown error"))
    if event.kind == "permission":
        tool = event.payload.get("tool", "?")
        return f"[ ? ] Allow {tool}? (y/a/n/p): "
    if event.kind == "done":
        return ""
    # text / reasoning: caller handles inline printing
    return ""


def banner() -> str:
    """First-line greeting for the classic REPL."""
    from eaccode import __version__ as _v
    return f"eaccode {_v}\n> ask anything. /help for commands. Ctrl+C to quit."
