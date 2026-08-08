"""Tool-call previews — Claude Code / OpenCode style.

Classic agent CLIs render a tool call as a compact call expression:
``⎿ read(path="src/main.py")`` — the tool name, the primary argument as
a keyword, no emojis, no boxes. Shell chains are summarized
(``git status && ls`` → ``git status + 1 command``).
"""
from __future__ import annotations

from dataclasses import dataclass

CHEVRON = "⎿"


# Primary argument shown in the one-line preview, per tool
_PRIMARY_ARGS = {
    "read": "path",
    "write": "path",
    "edit": "path",
    "bash": "command",
    "glob": "pattern",
    "grep": "pattern",
    "todo_write": "title",
    "web_fetch": "url",
    "web_search": "query",
    "skill_create": "name",
    "skill_patch": "name",
    "skill_list": "",
    "session_search": "query",
    "clarify": "question",
    "execute_code": "code",
    "delegate_task": "goal",
}

_SHELL_SILENT_HEADS = {
    "cd", "pushd", "popd", "export", "set", "unset", "source", ".", "true", "false", ":",
}


def _oneline(text: str) -> str:
    return " ".join(str(text).split())


def _truncate(text: str, max_len: int | None) -> str:
    if max_len and len(text) > max_len:
        if max_len <= 3:
            return "." * max_len
        return text[: max_len - 3] + "..."
    return text


def summarize_shell_command(command: str) -> str:
    """Compact shell chains: ``cd x && git status && ls`` → ``git status + 1 command``.

    Mirrors Hermes' summarize_shell_command: silent heads (cd, export,
    source, ...) are dropped; compound chains are collapsed.
    """
    import re

    original = _oneline(command)
    if not original:
        return ""
    # split on && or ; (naive, no quote handling — good enough for display)
    segments = [s.strip() for s in re.split(r"&&|;", original) if s.strip()]
    if len(segments) <= 1:
        return _truncate(original, 80)
    core: list[str] = []
    for seg in segments:
        head = seg.split()[0] if seg.split() else ""
        if head not in _SHELL_SILENT_HEADS:
            core.append(_truncate(seg, 60))
    if not core:
        return _truncate(original, 80)
    if len(core) == 1:
        return core[0]
    return f"{core[0]} + {len(core) - 1} {'command' if len(core) - 1 == 1 else 'commands'}"


def build_tool_preview(tool_name: str, args: dict, max_len: int = 90) -> str | None:
    """One-line preview of a tool call's primary argument, or None."""
    if not args:
        return None
    key = _PRIMARY_ARGS.get(tool_name)
    if key is None:  # unknown tool → show first non-empty value
        key = next((k for k, v in args.items() if v), None)
    if not key:
        return None
    value = args.get(key)
    if value is None:
        return None
    if tool_name == "bash":
        return summarize_shell_command(str(value))
    return _truncate(_oneline(value), max_len)


@dataclass
class ToolCallCard:
    """Everything the REPL needs to render one tool call (Claude-Code style)."""

    name: str
    call: str  # e.g. read(path="src/main.py") — no chevron, caller adds it
    duration_s: float | None = None
    ok: bool | None = None
    result_preview: str | None = None


def _quote(value) -> str:
    """Render an argument value like Claude Code: strings quoted, others bare."""
    if isinstance(value, str):
        if len(value) > 60:
            value = value[:57] + "..."
        return f'"{value}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_call_card(
    tool_name: str,
    args: dict,
    result: str | None = None,
    is_error: bool = False,
    duration_s: float | None = None,
    result_max: int = 100,
    full_args: bool = False,
) -> ToolCallCard:
    """Assemble the render data for one tool call.

    The call expression shows the primary argument by default
    (``read(path="src/main.py")``); with *full_args* every argument is
    included. bash commands are summarized for display.
    """
    key = _PRIMARY_ARGS.get(tool_name)
    if tool_name == "bash" and args.get("command"):
        rendered = f'bash(command="{summarize_shell_command(str(args["command"]))}")'
    elif full_args:
        parts = [f"{k}={_quote(v)}" for k, v in args.items() if v is not None]
        rendered = f"{tool_name}({', '.join(parts)})" if parts else tool_name
    elif key and args.get(key) is not None:
        rendered = f'{tool_name}({key}={_quote(args[key])})'
    else:
        rendered = tool_name
    return ToolCallCard(
        name=tool_name,
        call=rendered,
        duration_s=duration_s,
        ok=(not is_error) if result is not None else None,
        result_preview=_truncate(_oneline(result), result_max) if result else None,
    )


class VerboseLevel:
    """Tool-display verbosity, mirroring Hermes' /verbose cycle."""

    OFF = "off"        # only errors
    NEW = "new"        # tool name + preview (default)
    ALL = "all"        # + full arguments
    VERBOSE = "verbose"  # + full result previews

    CYCLE: list[str] = [OFF, NEW, ALL, VERBOSE]

    @classmethod
    def next(cls, current: str) -> str:
        idx = cls.CYCLE.index(current) if current in cls.CYCLE else 1
        return cls.CYCLE[(idx + 1) % len(cls.CYCLE)]

    @classmethod
    def show_start(cls, level: str) -> bool:
        return level in (cls.NEW, cls.ALL, cls.VERBOSE)

    @classmethod
    def show_result(cls, level: str, is_error: bool) -> bool:
        return is_error or level != cls.OFF

    @classmethod
    def show_full_args(cls, level: str) -> bool:
        return level in (cls.ALL, cls.VERBOSE)
