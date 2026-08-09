"""Slash-command handling — pure logic, UI-agnostic.

Dispatch is registry-driven: ``COMMAND_REGISTRY`` (command_def.py) is
the single source of truth for names, aliases, categories, and help
text; this module owns the handlers in ``DISPATCH_TABLE``. Autocomplete,
the command palette, and /help all derive from the same registry, so
they can never drift from what actually runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from eaccode.ui.command_def import get_command, help_text


@dataclass
class CommandResult:
    should_exit: bool = False
    message: str | None = None


def handle_command(text: str, app) -> CommandResult:
    """Dispatch a slash command (or return no-op for plain text)."""
    if not text.startswith("/"):
        return CommandResult()  # plain text → sent to the agent
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    entry = get_command(cmd)
    if entry is None:
        return CommandResult(message=f"Unknown command: {cmd}. Try /help.")

    handler = DISPATCH_TABLE.get(entry.name)
    if handler is None:
        return CommandResult(message=f"Command /{entry.name} is not wired yet.")
    return handler(app, arg)


# ---------------------------------------------------------------------------
# Handlers — one per canonical command name. Signature: (app, arg) -> CommandResult
# ---------------------------------------------------------------------------

def _cmd_exit(app, arg: str) -> CommandResult:
    return CommandResult(should_exit=True, message="Goodbye.")


def _cmd_help(app, arg: str) -> CommandResult:
    return CommandResult(message=help_text())


def _cmd_mode(app, arg: str) -> CommandResult:
    from eaccode.config.settings import PermissionMode

    if not arg:
        return CommandResult(
            message="Usage: /mode <default|acceptEdits|plan|smart|bypassPermissions>"
        )
    try:
        new_mode = PermissionMode(arg)
        app.policy.mode = new_mode
        app._mode_name = arg
        return CommandResult(message=f"Mode set to {arg}")
    except ValueError:
        return CommandResult(
            message="Unknown mode. Valid: default, acceptEdits, plan, smart, bypassPermissions"
        )


def _cmd_model(app, arg: str) -> CommandResult:
    if not arg:
        return CommandResult(
            message=f"Current model: {app._model_name or 'default'} (Usage: /model <name>)"
        )
    return CommandResult(message=app._switch_model(arg))


def _cmd_reasoning(app, arg: str) -> CommandResult:
    if arg in ("on", "1", "true"):
        app._show_reasoning = True
        return CommandResult(message="Reasoning display: on")
    if arg in ("off", "0", "false"):
        app._show_reasoning = False
        return CommandResult(message="Reasoning display: off")
    app._show_reasoning = not app._show_reasoning
    return CommandResult(message=f"Reasoning display: {'on' if app._show_reasoning else 'off'}")


def _cmd_undo(app, arg: str) -> CommandResult:
    n = 1
    if arg:
        try:
            n = max(1, int(arg))
        except ValueError:
            return CommandResult(message="Usage: /undo [N]")
    removed = 0
    while n > 0 and app.messages:
        app.messages.pop()
        removed += 1
        n -= 1
    return CommandResult(message=f"Removed {removed} message(s).")


def _cmd_retry(app, arg: str) -> CommandResult:
    if not app._last_prompt:
        return CommandResult(message="Nothing to retry yet.")
    return CommandResult(message=app._retry_last())


def _cmd_rollback(app, arg: str) -> CommandResult:
    from eaccode.tools.checkpoints import (
        list_checkpoints,
        restore_checkpoint,
    )

    cps = list_checkpoints(app.workdir)
    if not cps:
        return CommandResult(message="No checkpoints yet.")
    if not arg:
        lines = ["Checkpoints:"]
        for i, cp in enumerate(cps[:20]):
            lines.append(f"  {i}: {cp.stem} ({cp.stat().st_size} bytes)")
        lines.append("Restore with: /rollback <N>")
        return CommandResult(message="\n".join(lines))
    try:
        idx = int(arg)
        cp = cps[idx]
    except (ValueError, IndexError):
        return CommandResult(message=f"Invalid checkpoint index: {arg}")
    if restore_checkpoint(app.workdir, cp):
        return CommandResult(
            message=f"✓ Restored {cp.stem} — re-run your last prompt if needed."
        )
    return CommandResult(message="Restore failed.")


def _cmd_clear(app, arg: str) -> CommandResult:
    app.messages = []
    return CommandResult(message="Conversation cleared.")


def _cmd_copy(app, arg: str) -> CommandResult:
    app.action_copy_last()
    return CommandResult()


def _cmd_verbose(app, arg: str) -> CommandResult:
    from eaccode.ui.preview import VerboseLevel

    app.verbose_level = VerboseLevel.next(app.verbose_level)
    return CommandResult(message=f"Tool display: {app.verbose_level}")


def _cmd_memory(app, arg: str) -> CommandResult:
    facts = _get_memory(app)
    if not facts:
        return CommandResult(message="No learned facts for this project yet.")
    return CommandResult(message="\n".join(f"- {f}" for f in facts))


def _cmd_remember(app, arg: str) -> CommandResult:
    if not arg:
        return CommandResult(message="Usage: /remember <text>")
    _save_memory(app, arg)
    return CommandResult(message=f"Remembered: {arg}")


def _cmd_forget(app, arg: str) -> CommandResult:
    if not arg:
        return CommandResult(message="Usage: /forget <text>")
    _forget_memory(app, arg)
    return CommandResult(message=f"Forgot: {arg}")


def _cmd_cost(app, arg: str) -> CommandResult:
    if arg == "reset":
        usage = getattr(app, "_total_usage", None)
        if usage is not None:
            usage.__class__()
            app._total_usage = usage.__class__()
        return CommandResult(message="Usage counter reset.")
    usage = getattr(app, "last_usage", None)
    if usage:
        return CommandResult(
            message=f"Last run: {usage.input_tokens} in / {usage.output_tokens} out, "
            f"${usage.cost_usd:.4f}"
        )
    return CommandResult(message="No usage yet.")


def _cmd_status(app, arg: str) -> CommandResult:
    """/status — session, model, mode, tokens, cost, workdir (G.1)."""
    usage = getattr(app, "_total_usage", None)
    if usage is None:
        tokens_in = tokens_out = 0
        cost = 0.0
    else:
        tokens_in, tokens_out = usage.input_tokens, usage.output_tokens
        cost = usage.cost_usd
    lines = [
        f"Workdir: {app.workdir}",
        f"Model:   {app._model_name or 'default'}",
        f"Mode:    {app._mode_name or 'default'}",
        f"Tokens:  {tokens_in + tokens_out} ({tokens_in} in / {tokens_out} out)",
        f"Cost:    ${cost:.4f}",
    ]
    return CommandResult(message="\n".join(lines))


def _cmd_skills(app, arg: str) -> CommandResult:
    """/skills — list loaded skills, enable/disable for the session (G.6)."""
    arg = arg.strip()
    if arg.startswith("enable "):
        name = arg.split(None, 1)[1].strip()
        if hasattr(app, "_toggle_skill"):
            app._toggle_skill(name, enable=True)
            return CommandResult(message=f"Skill enabled: {name}")
        return CommandResult(message=f"Skill enabled: {name}")
    if arg.startswith("disable "):
        name = arg.split(None, 1)[1].strip()
        if hasattr(app, "_toggle_skill"):
            app._toggle_skill(name, enable=False)
            return CommandResult(message=f"Skill disabled: {name}")
        return CommandResult(message=f"Skill disabled: {name}")
    skills = getattr(app, "loaded_skills", None)
    if not skills:
        return CommandResult(message="No skills loaded for this session.")
    lines = ["Loaded skills:"]
    for s in skills:
        lines.append(f"  - {s}")
    return CommandResult(message="\n".join(lines))


def _cmd_compress(app, arg: str) -> CommandResult:
    """/compress [here N] — manual context compaction (G.3)."""
    from eaccode.agent.compaction import compact_messages

    if not hasattr(app, "messages") or not app.messages:
        return CommandResult(message="Nothing to compress yet.")
    before = len(app.messages)
    keep = None
    if arg.startswith("here "):
        try:
            keep = max(1, int(arg.split(None, 1)[1]))
        except ValueError:
            return CommandResult(message="Usage: /compress [here N]")
    app.messages = compact_messages(app.messages, keep_recent=keep or 5)
    after = len(app.messages)
    return CommandResult(
        message=f"Compressed: {before} → {after} messages"
        + (" (keeping last user turns)" if keep else "")
    )


def _cmd_diff(app, arg: str) -> CommandResult:
    """/diff [staged|all|session] — git diff for the session (G.2)."""
    from eaccode.ui.diff_cmd import run_diff

    mode = (arg or "staged").strip()
    if mode not in ("staged", "all", "session"):
        return CommandResult(message="Usage: /diff [staged|all|session]")
    return CommandResult(message=run_diff(mode, app))


DISPATCH_TABLE: dict[str, object] = {
    "exit": _cmd_exit,
    "help": _cmd_help,
    "mode": _cmd_mode,
    "model": _cmd_model,
    "reasoning": _cmd_reasoning,
    "undo": _cmd_undo,
    "retry": _cmd_retry,
    "rollback": _cmd_rollback,
    "clear": _cmd_clear,
    "copy": _cmd_copy,
    "verbose": _cmd_verbose,
    "memory": _cmd_memory,
    "remember": _cmd_remember,
    "forget": _cmd_forget,
    "cost": _cmd_cost,
    "status": _cmd_status,
    "skills": _cmd_skills,
    "compress": _cmd_compress,
    "diff": _cmd_diff,
}


# ---------------------------------------------------------------------------
# Memory helpers — sync (MemoryStore ops are plain file IO; asyncio.run from
# inside Textual's running loop raises RuntimeError, Phase A.6).
# ---------------------------------------------------------------------------

def _get_memory(app) -> list[str]:
    if hasattr(app, "memory_facts") and app.memory_facts:
        return app.memory_facts
    store = getattr(app, "memory_store", None)
    if store is not None:
        project_hash_fn = getattr(type(app), "project_hash", None)
        if project_hash_fn is not None:
            return store.recall_sync(project_hash_fn(app.workdir))
    return []


def _save_memory(app, text: str) -> None:
    store = getattr(app, "memory_store", None)
    if store is not None:
        project_hash_fn = getattr(type(app), "project_hash", None)
        if project_hash_fn is not None:
            store.remember_sync(project_hash_fn(app.workdir), text, source="user")


def _forget_memory(app, text: str) -> None:
    store = getattr(app, "memory_store", None)
    if store is not None:
        project_hash_fn = getattr(type(app), "project_hash", None)
        if project_hash_fn is not None:
            store.forget_sync(project_hash_fn(app.workdir), text)
