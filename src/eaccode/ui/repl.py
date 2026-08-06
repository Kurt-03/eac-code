"""Textual REPL (Task 7.1) — interactive chat with the agent.

Layout: chat log (top) + input (bottom). Slash commands handled by
ui.commands; agent built by agent.factory (project context + memory + skills).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from rich.panel import Panel
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, RichLog

from eaccode.agent.factory import build_agent
from eaccode.config.paths import EaccodePaths
from eaccode.memory.store import MemoryStore
from eaccode.ui.commands import handle_command


class EaccodeApp(App):
    TITLE = "eaccode"

    CSS = """
    #log {
        height: 90%;
        border: round $primary;
        padding: 0 1;
    }
    #input {
        height: 3;
        border: round $accent;
    }
    """

    def __init__(self, workdir: Path | None = None) -> None:
        super().__init__()
        self.workdir = (workdir or Path.cwd()).resolve()
        self.messages: list = []
        self.last_usage = None
        self.memory_facts: list[str] = []
        self.memory_store: MemoryStore | None = None
        self._agent = None
        self._client = None
        self._no_providers = False
        self._error = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield RichLog(id="log", wrap=True, markup=True, highlight=True)
            yield Input(placeholder="Ask eaccode anything... (/help for commands)", id="input")

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write(
            Panel.fit(
                f"[bold cyan]eaccode[/bold cyan] — coding agent\n"
                f"workdir: {self.workdir}\n"
                f"Type /help for commands, /exit to quit.",
                border_style="cyan",
            )
        )
        try:
            agent, client, sysctx = build_agent(self.workdir)
            self._agent, self._client = agent, client
            self.memory_facts = sysctx.memory_facts
            if sysctx.memory_facts:
                log.write("[dim]Loaded memory:[/dim]")
                for f in sysctx.memory_facts:
                    log.write(f"[dim]  • {f}[/dim]")
        except RuntimeError as e:
            self._no_providers = True
            self._error = str(e)
            log.write(Panel.fit(f"[red]{e}[/red]", border_style="red"))

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        log = self.query_one("#log", RichLog)
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        log.write(Panel.fit(f"[bold blue]❯[/bold blue] {text}", border_style="blue"))

        if text.startswith("/"):
            result = handle_command(text, self)
            if result.message:
                log.write(result.message)
            if result.should_exit:
                self.exit()
            return

        if self._no_providers:
            log.write(f"[red]{self._error}[/red]")
            return

        self.messages.append({"role": "user", "content": text})
        log.write("[dim]eaccode is working…[/dim]")
        try:
            result = await self._run_agent([self.messages[-1]])
            log.write(result)
            self.last_usage = self._agent_last_usage()
        except Exception as e:
            log.write(Panel.fit(f"[red]Error: {e}[/red]", border_style="red"))

    async def _run_agent(self, new_messages: list) -> str:
        """Run the loop on the full history, return the final text."""
        from eaccode.llm.models import Message

        # rebuild full history from our message list
        history = []
        for m in self.messages:
            if m["role"] == "user":
                history.append(Message.user(m["content"]))
            else:
                history.append(Message.assistant(m["content"]))
        result = await self._agent.run(history)
        # keep only the assistant text for display history
        self.messages.append({"role": "assistant", "content": result.final_text})
        return result.final_text

    def _agent_last_usage(self):
        if self._agent is not None and hasattr(self._agent, "last_result"):
            return self._agent.last_result.usage
        return None


def run_repl(workdir: Path | None = None) -> None:
    EaccodeApp(workdir=workdir).run()
