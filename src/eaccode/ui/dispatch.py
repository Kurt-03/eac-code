"""Dispatch a slash-command for the classic REPL.

Wraps the existing ``eaccode.ui.commands.handle_command`` (which expects
a Textual App) and adapts it to a plain-string return so the REPL loop
can just print it.
"""

from __future__ import annotations

from eaccode.ui.commands import handle_command as _handle_command
from eaccode.ui.context import ReplContext, _CtxProxy


def dispatch_slash(text: str, ctx: ReplContext) -> tuple[str, bool]:
    """Run *text* (e.g. ``/mode safeAuto``).

    Returns ``(output, should_exit)``.
    """
    proxy = _CtxProxy(ctx)
    try:
        result = _handle_command(text, proxy)
    except SystemExit:
        # handle_command may call sys.exit (e.g. /exit).
        return "bye.", True
    except Exception as e:
        return f"[ X ] slash command failed: {e}", False
    msg = getattr(result, "message", "")
    if msg:
        # Strip Rich markup the REPL cannot render.
        msg = _strip_markup(msg)
    return msg, bool(getattr(result, "should_exit", False))


def _strip_markup(text: str) -> str:
    """Drop Rich markup tags — the classic REPL has no Log widget."""
    import re

    return re.sub(r"\[/?[^\]]+\]", "", text)
