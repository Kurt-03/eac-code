"""Slash-command handling (Task 7.2) — pure logic, UI-agnostic."""
from __future__ import annotations

from dataclasses import dataclass

HELP_TEXT = """Slash commands:
  /help                 Show this help
  /mode <name>          Switch permission mode (default|acceptEdits|plan|smart|bypassPermissions)
  /model <name>         Switch model/provider for the next turns (e.g. /model opencode-go)
  /reasoning [on|off]   Show or hide the model's reasoning tokens
  /verbose              Cycle tool display: off → new → all → verbose
  /undo [N]             Remove the last N exchanges (user+assistant)
  /retry                Re-run the last prompt
  /rollback [N]         List file checkpoints; restore one with an index
  /memory               Show learned project facts
  /remember <text>      Save a project fact
  /forget <text>        Remove a project fact
  /cost                 Show token usage and cost of the last run
  /copy                 Copy the last assistant answer to the clipboard
  /clear                Clear conversation history
  /exit                 Exit eaccode

Keys:  Ctrl+C cancel/quit · Ctrl+Y copy last answer
Hint:  Textual owns the mouse, so the terminal's own text selection is
       disabled — use /copy (last answer) instead.
"""


@dataclass
class CommandResult:
    should_exit: bool = False
    message: str | None = None


def handle_command(text: str, app) -> CommandResult:
    if not text.startswith("/"):
        return CommandResult()  # plain text → sent to the agent
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/exit", "/quit"):
        return CommandResult(should_exit=True, message="Goodbye.")
    if cmd == "/help":
        return CommandResult(message=HELP_TEXT)
    if cmd == "/mode":
        try:
            from eaccode.config.settings import PermissionMode

            new_mode = PermissionMode(arg)
            app.policy.mode = new_mode
            app._mode_name = arg
            return CommandResult(message=f"Mode set to {arg}")
        except ValueError:
            return CommandResult(
                message="Unknown mode. Valid: default, acceptEdits, plan, smart, bypassPermissions"
            )
    if cmd == "/model":
        if not arg:
            return CommandResult(
                message=f"Current model: {app._model_name or 'default'} (Usage: /model <name>)"
            )
        return CommandResult(message=app._switch_model(arg))
    if cmd == "/reasoning":
        if arg in ("on", "1", "true"):
            app._show_reasoning = True
            return CommandResult(message="Reasoning display: on")
        if arg in ("off", "0", "false"):
            app._show_reasoning = False
            return CommandResult(message="Reasoning display: off")
        app._show_reasoning = not app._show_reasoning
        return CommandResult(message=f"Reasoning display: {'on' if app._show_reasoning else 'off'}")
    if cmd == "/undo":
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
    if cmd == "/retry":
        if not app._last_prompt:
            return CommandResult(message="Nothing to retry yet.")
        return CommandResult(message=app._retry_last())
    if cmd == "/rollback":
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
    if cmd == "/clear":
        app.messages = []
        return CommandResult(message="Conversation cleared.")
    if cmd == "/copy":
        app.action_copy_last()
        return CommandResult()
    if cmd == "/verbose":
        from eaccode.ui.preview import VerboseLevel

        app.verbose_level = VerboseLevel.next(app.verbose_level)
        return CommandResult(message=f"Tool display: {app.verbose_level}")
    if cmd == "/memory":
        facts = _get_memory(app)
        if not facts:
            return CommandResult(message="No learned facts for this project yet.")
        return CommandResult(message="\n".join(f"- {f}" for f in facts))
    if cmd == "/remember":
        if not arg:
            return CommandResult(message="Usage: /remember <text>")
        _save_memory(app, arg)
        return CommandResult(message=f"Remembered: {arg}")
    if cmd == "/forget":
        if not arg:
            return CommandResult(message="Usage: /forget <text>")
        _forget_memory(app, arg)
        return CommandResult(message=f"Forgot: {arg}")
    if cmd == "/cost":
        usage = getattr(app, "last_usage", None)
        if usage:
            return CommandResult(
                message=f"Last run: {usage.input_tokens} in / {usage.output_tokens} out, "
                f"${usage.cost_usd:.4f}"
            )
        return CommandResult(message="No usage yet.")
    return CommandResult(message=f"Unknown command: {cmd}. Try /help.")


def _get_memory(app) -> list[str]:
    if hasattr(app, "memory_facts") and app.memory_facts:
        return app.memory_facts
    store = getattr(app, "memory_store", None)
    if store is not None:
        # Sync path: MemoryStore ops are plain file IO; calling
        # asyncio.run() from inside Textual's running loop raises
        # RuntimeError (Phase A.6).
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
