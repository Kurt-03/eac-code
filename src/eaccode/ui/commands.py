"""Slash-command handling (Task 7.2) — pure logic, UI-agnostic."""
from __future__ import annotations

from dataclasses import dataclass

HELP_TEXT = """Slash commands:
  /help                 Show this help
  /mode <name>          Switch permission mode (default|acceptEdits|plan|bypassPermissions)
  /memory               Show learned project facts
  /remember <text>      Save a project fact
  /forget <text>        Remove a project fact
  /cost                 Show token usage and cost of the last run
  /clear                Clear conversation history
  /exit                 Exit eaccode
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
            return CommandResult(message=f"Mode set to {arg}")
        except ValueError:
            return CommandResult(
                message="Unknown mode. Valid: default, acceptEdits, plan, bypassPermissions"
            )
    if cmd == "/clear":
        app.messages = []
        return CommandResult(message="Conversation cleared.")
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
        import asyncio

        return asyncio.run(
            store.recall(type(app).project_hash(app.workdir))
        ) if hasattr(type(app), "project_hash") else []
    return []


def _save_memory(app, text: str) -> None:
    store = getattr(app, "memory_store", None)
    if store is not None:
        import asyncio

        asyncio.run(store.remember(type(app).project_hash(app.workdir), text, source="user"))


def _forget_memory(app, text: str) -> None:
    store = getattr(app, "memory_store", None)
    if store is not None:
        import asyncio

        asyncio.run(store.forget(type(app).project_hash(app.workdir), text))
