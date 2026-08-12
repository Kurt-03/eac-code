"""Permission confirmation (Phase B.1) — in-REPL modal replaces click.confirm.

The old implementation used ``click.confirm`` which reads stdin. Inside
the Textual REPL stdin belongs to the UI, so every ASK-mode tool call was
silently denied (``sys.stdin.isatty()`` is False in the app context).
Users never saw a prompt — the worst kind of UX failure.

The new flow: the permission layer returns a choice (allow-once /
allow-always / deny). The REPL renders a Textual modal; the agent loop
awaits the modal's Future. Headless contexts (CI, pipes, queue jobs)
keep deny-by-default, but the reason is explicit.

No ``asyncio.run`` anywhere: the async variant awaits a Future that the
UI resolves, which is the only loop-safe pattern inside Textual.
"""

from __future__ import annotations

import enum
import sys

from eaccode.permissions.rules import Action, Rule


class PermissionChoice(str, enum.Enum):  # noqa: UP042  (str value for JSON/schema compat)
    ALLOW_ONCE = "allow-once"
    ALLOW_SESSION = "allow-session"  # v0.0.1: remember for the session, no persist
    ALLOW_ALWAYS = "allow-always"
    DENY = "deny"
    PAUSE = "pause"  # P0.8: pause the session — no further tool calls


# How long the REPL modal waits before denying. v0.4.0 raised this
# from 60s to 10 minutes: real users pause to read multi-line diffs,
# and a stuck-by-typo REPL that auto-denies after 1 minute is hostile.
# The fail-closed default still kicks in if the user walks away.
MODAL_TIMEOUT_SECONDS = 600.0


def _describe(tool: str, arguments: dict) -> str:
    if tool == "bash":
        return arguments.get("command", "")
    if tool in ("write", "edit"):
        path = arguments.get("path", "")
        if tool == "edit":
            return f"{path}: replace {arguments.get('old_string', '')[:60]!r}"
        return f"{path} ({len(arguments.get('content', ''))} bytes)"
    return str(arguments)[:120]


def build_permission_question(tool: str, arguments: dict) -> str:
    """Human-readable question for the modal header."""
    detail = _describe(tool, arguments)
    if tool == "bash":
        return f"Run command? [{detail}]"
    if tool in ("write", "edit"):
        return f"Modify file? [{detail}]"
    return f"Allow {tool}? [{detail}]"


def prompt_for_permission(
    tool: str,
    arguments: dict,
    *,
    session_rules: list[Rule] | None = None,
    ask_callback=None,
    pause_flag=None,
) -> bool:
    """SYNC ask (legacy/headless path). Returns True if approved.

    ``ask_callback`` is a sync ``callable(question: str) -> PermissionChoice``.
    When None, falls back to click.confirm on TTYs; non-TTY denies.
    The REPL must use :func:`prompt_for_permission_async` instead.
    ``pause_flag`` (P0.8): a PAUSE choice pauses the session.
    """
    if ask_callback is not None:
        choice = ask_callback(build_permission_question(tool, arguments))
        return _handle_choice(choice, tool, arguments, session_rules, pause_flag)

    # Headless / legacy path.
    if not sys.stdin.isatty():
        return False  # non-interactive: deny rather than hang
    import click

    granted = click.confirm(build_permission_question(tool, arguments), default=False)
    if granted and session_rules is not None:
        _remember_rule(session_rules, tool, arguments)
    return granted


async def prompt_for_permission_async(
    tool: str,
    arguments: dict,
    *,
    session_rules: list[Rule] | None = None,
    ask_async=None,
    timeout: float = MODAL_TIMEOUT_SECONDS,
    pause_flag=None,
) -> bool:
    """ASYNC ask for the REPL. Awaits the modal's Future (loop-safe).

    ``ask_async(question: str) -> asyncio.Future[PermissionChoice]`` —
    the UI pushes the modal and resolves the Future on button press.
    Timeout (default 60s) → DENY (fail closed, like the non-TTY path).
    ``pause_flag`` (P0.8): a PAUSE choice pauses the session.
    """
    import asyncio

    if ask_async is None:
        return prompt_for_permission(
            tool, arguments, session_rules=session_rules, pause_flag=pause_flag
        )

    question = build_permission_question(tool, arguments)
    future = ask_async(question)
    try:
        choice = await asyncio.wait_for(future, timeout=timeout)
    except (TimeoutError, asyncio.CancelledError):
        choice = PermissionChoice.DENY  # modal timed out / never resolved
    except Exception:
        choice = PermissionChoice.DENY  # modal failed — fail closed
    return _handle_choice(choice, tool, arguments, session_rules, pause_flag)


def _handle_choice(
    choice: PermissionChoice,
    tool: str,
    arguments: dict,
    session_rules: list[Rule] | None,
    pause_flag,
) -> bool:
    """Shared choice handling for sync + async ask paths (P0.8).

    Branching:
    - ALLOW_ALWAYS: remember the rule in *session_rules* AND the caller
      is responsible for persisting to the allowlist (via the policy
      layer). This is the only path that touches persistent storage.
    - ALLOW_SESSION: remember the rule in *session_rules* only. The rule
      is lost on restart. No allowlist write.
    - ALLOW_ONCE: grant the call, remember nothing.
    - DENY / PAUSE: refuse.
    """
    if choice == PermissionChoice.ALLOW_ALWAYS and session_rules is not None:
        _remember_rule(session_rules, tool, arguments)
    if choice == PermissionChoice.PAUSE:
        if pause_flag is not None:
            pause_flag.pause()
        return False
    return choice in (
        PermissionChoice.ALLOW_ONCE,
        PermissionChoice.ALLOW_SESSION,
        PermissionChoice.ALLOW_ALWAYS,
    )


def _remember_rule(session_rules: list[Rule], tool: str, arguments: dict) -> None:
    """Remember "always allow this command pattern" for the session."""
    if tool == "bash":
        head = arguments.get("command", "").split()[0] if arguments.get("command") else "*"
        session_rules.append(Rule(tool=tool, action=Action.ALLOW, pattern=f"{head} *"))
    else:
        session_rules.append(Rule(tool=tool, action=Action.ALLOW, pattern="*"))
