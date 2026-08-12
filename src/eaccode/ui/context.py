"""Slash-command dispatch for the classic REPL.

The classic REPL has no Textual ``App`` object — instead, it carries a
``ReplContext`` dataclass with the attributes slash-commands need
(policy, agent, allowlist, messages, paths, etc).

To avoid rewriting every existing ``_cmd_*`` function in
``eaccode/ui/commands.py`` (they all use ``getattr(app, ...)``), we
build a tiny attribute proxy at runtime: every attribute access on
the proxy delegates to the ``ReplContext``. ``handle_command`` keeps
working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReplContext:
    """Everything a slash-command needs to read or mutate."""

    workdir: Path | None = None
    agent: Any = None
    policy: Any = None
    allowlist: Any = None
    approvals: Any = None
    pause_flag: Any = None
    verbose_level: int = 1
    show_reasoning: bool = False
    # Mutable bag the REPL updates as the conversation evolves.
    state: dict = field(default_factory=dict)
    # Output buffer — handle_command writes CommandResult.message into
    # here; the REPL loop prints it.
    output: list[str] = field(default_factory=list)
    # When a command should exit the REPL entirely, set this to True.
    should_exit: bool = False


class _CtxProxy:
    """Attribute access proxy — translates ``app.<x>`` to ``ctx.<x>``.

    Falls back to the state dict so commands that read ad-hoc attributes
    (e.g. ``_refresh_status_rule``) keep working when the proxy returns
    None — the existing ``getattr(app, ...)`` pattern handles ``None``
    gracefully (prints "No X in this context.").
    """

    def __init__(self, ctx: ReplContext) -> None:
        # Bypass our own __setattr__ (which would shove everything into
        # the state bag) for the constructor.
        object.__setattr__(self, "_ctx", ctx)

    def __getattr__(self, name: str):
        # __getattr__ is only called when normal lookup fails. We have
        # not set anything else on the proxy, so this path is safe.
        ctx = object.__getattribute__(self, "_ctx")
        if name in ctx.__dataclass_fields__:
            return getattr(ctx, name)
        if name in ctx.state:
            return ctx.state[name]
        aliases = {
            "_agent": "agent",
            "_policy": "policy",
            "_allowlist": "allowlist",
            "_approvals": "approvals",
            "_pause_flag": "pause_flag",
            "_verbose_level": "verbose_level",
            "_show_reasoning": "show_reasoning",
            "messages": "messages",
            "workdir": "workdir",
        }
        if name in aliases:
            return getattr(ctx, aliases[name], None)
        return None

    def __setattr__(self, name: str, value: Any) -> None:
        # Constructor already set _ctx; preserve it. Anything else is
        # an alias or a state-bag entry.
        if name == "_ctx":
            object.__setattr__(self, name, value)
            return
        ctx = object.__getattribute__(self, "_ctx")
        aliases = {
            "_agent": "agent",
            "_policy": "policy",
            "_allowlist": "allowlist",
            "_approvals": "approvals",
            "_pause_flag": "pause_flag",
            "_verbose_level": "verbose_level",
            "_show_reasoning": "show_reasoning",
        }
        if name in aliases:
            setattr(ctx, aliases[name], value)
            return
        ctx.state[name] = value
