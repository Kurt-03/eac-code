"""Command palette — Ctrl+K modal, filterable command list.

Hermes' desktop app has ⌘K; Claude Code has Tab-cycle. A filterable
palette is the highest-leverage input feature: every command + its
description visible, type to filter, Enter to run — works even for
commands with long names.
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static

from eaccode.ui.command_def import COMMAND_REGISTRY, CommandDef


class CommandPalette(ModalScreen):
    """Filterable slash-command list. Enter runs, Esc closes."""

    BINDINGS: ClassVar = [
        Binding("escape", "close", "Close"),
        Binding("enter", "run_selected", "Run"),
        Binding("ctrl+k", "close", "Close"),
    ]

    def __init__(self, on_run=None) -> None:
        super().__init__()
        self._on_run = on_run or (lambda name: None)
        self._commands = COMMAND_REGISTRY

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-box"):
            yield Input(placeholder="Filter commands…  (/status, /diff, …)", id="palette-filter")
            yield ListView(id="palette-list")

    def on_mount(self) -> None:
        self.query_one("#palette-filter", Input).focus()
        self._render(self._commands)

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip().lstrip("/").lower()
        if not query:
            self._render(self._commands)
            return
        matches = [
            c for c in self._commands
            if query in c.name.lower()
            or query in c.description.lower()
            or any(query in a.lower() for a in c.aliases)
        ]
        self._render(matches)

    def _render(self, commands: list[CommandDef]) -> None:
        view = self.query_one("#palette-list", ListView)
        view.clear()
        for cmd in commands:
            label = f"/{cmd.name} — {cmd.description}"
            view.append(ListItem(Static(label, id=f"pal-{cmd.name}")))

    def action_run_selected(self) -> None:
        view = self.query_one("#palette-list", ListView)
        if view.index is None:
            return
        item = view.children[view.index]
        static = item.query_one(Static)
        name = (static.id or "").removeprefix("pal-")
        self._on_run(f"/{name}")
        self.dismiss()

    def action_close(self) -> None:
        self.dismiss()
