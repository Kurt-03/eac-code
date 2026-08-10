"""Command registry — the single source of truth for slash commands.

Ported from Hermes' ``COMMAND_REGISTRY`` pattern (``hermes_cli/commands.py``).
One ``CommandDef`` per slash command carries its name, aliases, category,
description, argument hint, and subcommands. Everything that displays or
dispatches commands — autocomplete (F.2), the command palette (F.3),
``/help`` (G.7) — derives from this registry, so the help text can never
drift from the code.

Categories mirror Hermes: Session, Configuration, Tools & Skills, Info,
Exit.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandDef:
    """Definition of a single slash command.

    Data only — handlers live in ``eaccode.ui.commands.DISPATCH_TABLE``
    (keyed by canonical name), so this module never imports the UI layer
    (no circular imports). The registry is the single source of truth
    for autocomplete, /help, and the command palette.
    """

    name: str                          # canonical name without slash: "undo"
    description: str                   # human-readable one-liner
    category: str                      # "Session", "Configuration", ...
    aliases: tuple[str, ...] = ()
    args_hint: str = ""                # argument placeholder: "[N]", "<name>"
    subcommands: tuple[str, ...] = ()  # tab-completable subcommands
    # Commands that open pickers when run without arguments must NOT get a
    # trailing space in completions — Enter should execute them (Hermes
    # _PICKER_COMMANDS semantics).
    picker: bool = False


# Every dispatchable command, in /help display order.
COMMAND_REGISTRY: list[CommandDef] = [
    # ── Session ──────────────────────────────────────────────────────────
    CommandDef("undo", "Remove the last N exchanges (user+assistant)",
               "Session", args_hint="[N]"),
    CommandDef("retry", "Re-run the last prompt", "Session"),
    CommandDef("rollback", "List file checkpoints; restore one with an index",
               "Session", args_hint="[N]"),
    CommandDef("clear", "Clear conversation history", "Session"),
    CommandDef("status", "Show session, model, tokens, ctx%, workdir",
               "Session"),
    # ── Configuration ────────────────────────────────────────────────────
    CommandDef("mode", "Switch permission mode (default|acceptEdits|plan|smart|bypassPermissions)",
               "Configuration", args_hint="<name>",
               subcommands=("default", "acceptEdits", "plan", "smart", "bypassPermissions"),
               picker=True),
    CommandDef("model", "Switch model/provider for the next turns",
               "Configuration", args_hint="<name>", picker=True),
    CommandDef("reasoning", "Show or hide the model's reasoning tokens",
               "Configuration", args_hint="[on|off]",
               subcommands=("on", "off"), picker=True),
    CommandDef("verbose", "Cycle tool display: off → new → all → verbose",
               "Configuration", args_hint="[off|new|all|verbose]",
               subcommands=("off", "new", "all", "verbose"), picker=True),
    # ── Tools & Skills ───────────────────────────────────────────────────
    CommandDef("memory", "Show learned project facts", "Tools & Skills"),
    CommandDef("remember", "Save a project fact", "Tools & Skills",
               args_hint="<text>"),
    CommandDef("forget", "Remove a project fact", "Tools & Skills",
               args_hint="<text>"),
    CommandDef("skills", "List loaded skills (browse/enable/disable)",
               "Tools & Skills", args_hint="[enable|disable <name>]",
               subcommands=("enable", "disable")),
    CommandDef("compress", "Manually compact context", "Tools & Skills",
               args_hint="[here N]"),
    CommandDef("diff", "Show git diff (staged|all|session)", "Tools & Skills",
               args_hint="[staged|all|session]",
               subcommands=("staged", "all", "session")),
    # ── Info ─────────────────────────────────────────────────────────────
    CommandDef("help", "Show this help", "Info", aliases=("?",)),
    CommandDef("cost", "Show token usage and cost (reset with /cost reset)",
               "Info", args_hint="[reset]", subcommands=("reset",)),
    CommandDef("copy", "Copy the last assistant answer to the clipboard",
               "Info", args_hint="[N]"),
    # ── Exit ─────────────────────────────────────────────────────────────
    CommandDef("exit", "Exit eaccode", "Exit", aliases=("quit",)),
]


# name/alias → CommandDef, for O(1) dispatch lookup.
_COMMAND_INDEX: dict[str, CommandDef] = {}
for _cmd in COMMAND_REGISTRY:
    _COMMAND_INDEX[_cmd.name] = _cmd
    for _alias in _cmd.aliases:
        _COMMAND_INDEX[_alias] = _cmd


def get_command(name: str) -> CommandDef | None:
    """Look up a command by canonical name or alias (with or without '/').

    Returns None for unknown commands.
    """
    return _COMMAND_INDEX.get(name.lstrip("/").lower())


def register_command(cmd: CommandDef) -> None:
    """Add a runtime command (Phase I.12 — plugin slash commands).

    Keeps the registry and the O(1) index in sync. Built-ins are
    registered at import time; plugins register during startup.
    """
    COMMAND_REGISTRY.append(cmd)
    _COMMAND_INDEX[cmd.name] = cmd
    for alias in cmd.aliases:
        _COMMAND_INDEX[alias] = cmd


def all_command_names() -> list[str]:
    """Every dispatchable name incl. aliases, each prefixed with '/'."""
    names: list[str] = []
    for cmd in COMMAND_REGISTRY:
        names.append(f"/{cmd.name}")
        names.extend(f"/{a}" for a in cmd.aliases)
    return names


def help_text() -> str:
    """Render /help grouped by category, from the registry (G.7)."""
    lines = ["Slash commands:"]
    current_category = None
    for cmd in COMMAND_REGISTRY:
        if cmd.category != current_category:
            current_category = cmd.category
            lines.append(f"\n  {current_category}:")
        hint = f" {cmd.args_hint}" if cmd.args_hint else ""
        lines.append(f"    /{cmd.name}{hint:<22} {cmd.description}")
    lines.append("\nKeys:  Ctrl+C cancel/quit · Ctrl+Y copy last answer")
    return "\n".join(lines)
