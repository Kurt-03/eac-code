"""Permission confirmation prompts (Task 4.2).

Interactive y/n confirmations when the policy returns ASK. In non-TTY
contexts (CI, pipes, headless queue jobs) the prompt never blocks —
it denies by default.
"""
from __future__ import annotations

import sys

import click

from eaccode.permissions.rules import Action, Rule


def prompt_for_permission(
    tool: str,
    arguments: dict,
    *,
    session_rules: list[Rule] | None = None,
) -> bool:
    """Ask the user to allow a tool call. Returns True if approved."""
    if not sys.stdin.isatty():
        return False  # non-interactive: deny rather than hang

    detail = _describe(tool, arguments)
    if tool == "bash":
        question = f"Run command? [{detail}]"
    elif tool in ("write", "edit"):
        question = f"Modify file? [{detail}]"
    else:
        question = f"Allow {tool}? [{detail}]"

    granted = click.confirm(question, default=False)
    if granted and session_rules is not None and tool == "bash":
        # Remember "always allow this command pattern" for the session
        head = arguments.get("command", "").split()[0] if arguments.get("command") else "*"
        session_rules.append(Rule(tool=tool, action=Action.ALLOW, pattern=f"{head} *"))
    return granted


def _describe(tool: str, arguments: dict) -> str:
    if tool == "bash":
        return arguments.get("command", "")
    if tool in ("write", "edit"):
        path = arguments.get("path", "")
        if tool == "edit":
            return f"{path}: replace {arguments.get('old_string', '')[:60]!r}"
        return f"{path} ({len(arguments.get('content', ''))} bytes)"
    return str(arguments)[:120]
