"""Permission modal (Phase B.1/B.2) — y/n/a with inline diff for write/edit.

A Textual ModalScreen. The REPL pushes it when the policy says ASK; the
agent loop awaits its Future (see ``prompt_for_permission_async``). The
modal shows the tool + primary argument, an inline unified diff for
write/edit calls, and three actions: y (allow once), a (always allow for
the session), n (deny). Escape = deny. A 60s timeout denies (handled by
the caller).
"""

from __future__ import annotations

import difflib
from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from eaccode.permissions.prompts import PermissionChoice


def build_unified_diff(old_text: str, new_text: str, path: str = "file") -> str:
    """Render a unified diff between two strings (Phase B.2)."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{path}", tofile=f"b/{path}",
            lineterm="",
        )
    )


def diff_for_write(path: Path, content: str, max_lines: int = 30) -> str | None:
    """Diff for a write call: empty file → content (all additions).

    Returns None when the diff would be huge (cap 30 lines of context).
    """
    if path.exists():
        old = path.read_text(encoding="utf-8", errors="replace")
        diff = build_unified_diff(old, content, str(path))
    else:
        # New file: everything is an addition.
        lines = content.splitlines()
        diff = f"--- a/{path}\n+++ b/{path}\n"
        diff += "\n".join(f"+{ln}" for ln in lines[: max_lines - 4])
        if len(lines) > max_lines - 4:
            diff += f"\n+… ({len(lines) - (max_lines - 4)} more lines)"
        diff = "\n".join([*diff.splitlines()[:max_lines],
                          f"… ({len(diff.splitlines()) - max_lines} more lines)"]) \
            if len(diff.splitlines()) > max_lines else diff
    return diff


class PermissionModal(ModalScreen):
    """y = allow once · a = always allow · n = deny. Esc = deny."""

    BINDINGS: ClassVar = [
        Binding("y", "allow_once", "Allow once"),
        Binding("a", "allow_always", "Always allow"),
        Binding("n", "deny", "Deny"),
        Binding("escape", "deny", "Deny"),
    ]

    def __init__(self, tool: str, arguments: dict, question: str,
                 resolve: Callable[[PermissionChoice], None] | None = None) -> None:
        super().__init__()
        self._tool = tool
        self._arguments = arguments
        self._question = question
        # resolve(choice) is called on button press; the REPL wires it to
        # the asyncio.Future the agent loop awaits.
        self._resolve_cb = resolve or (lambda choice: None)

    def compose(self) -> ComposeResult:
        with Vertical(id="perm-box"):
            yield Static(self._question, id="perm-question")
            diff = self._diff_preview()
            if diff:
                yield Static(diff, id="perm-diff")
            with Horizontal(id="perm-actions"):
                yield Button("Allow once (y)", id="perm-y", variant="primary")
                yield Button("Always allow (a)", id="perm-a", variant="success")
                yield Button("Deny (n)", id="perm-n", variant="error")

    def on_mount(self) -> None:
        self.query_one("#perm-y", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "perm-y":
            self.action_allow_once()
        elif event.button.id == "perm-a":
            self.action_allow_always()
        elif event.button.id == "perm-n":
            self.action_deny()

    def _diff_preview(self) -> str | None:
        """Inline diff for write/edit calls (Phase B.2)."""
        if self._tool not in ("write", "edit"):
            return None
        path = Path(self._arguments.get("path", ""))
        if not path.is_absolute():
            # Workdir-relative paths: resolve against the REPL cwd when
            # available (the app sets workdir on the modal via set_app).
            app = getattr(self, "app", None)
            base = getattr(app, "workdir", Path.cwd())
            path = base / path
        if self._tool == "write":
            content = self._arguments.get("content", "")
            diff = diff_for_write(path, content)
        else:
            old_string = self._arguments.get("old_string", "")
            new_string = self._arguments.get("new_string", "")
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="replace")
                diff = build_unified_diff(
                    text.replace(old_string, new_string, 1) if old_string else text,
                    text,
                    str(path),
                )
            else:
                return None
        return diff

    def action_allow_once(self) -> None:
        self._resolve_cb(PermissionChoice.ALLOW_ONCE)
        self.dismiss()

    def action_allow_always(self) -> None:
        self._resolve_cb(PermissionChoice.ALLOW_ALWAYS)
        self.dismiss()

    def action_deny(self) -> None:
        self._resolve_cb(PermissionChoice.DENY)
        self.dismiss()
