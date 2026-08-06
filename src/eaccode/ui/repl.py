"""Textual REPL (Task 7.1/7.3) — interactive chat with live streaming.

Layout: chat log + live stream preview + input. Slash commands handled by
ui.commands; agent built by agent.factory (project context + memory + skills).
Streaming shows text deltas live and tool calls as cards (Task 7.3).
"""
from __future__ import annotations

from pathlib import Path

from rich.panel import Panel
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, RichLog, Static

from eaccode.agent.factory import build_agent
from eaccode.llm.models import ToolCall
from eaccode.memory.store import MemoryStore
from eaccode.tools.base import ToolResult
from eaccode.ui.commands import handle_command


class EaccodeApp(App):
    TITLE = "eaccode"

    CSS = """
    #log {
        height: 80%;
        border: round $primary;
        padding: 0 1;
    }
    #stream {
        height: auto;
        max-height: 8;
        color: $text-muted;
        padding: 0 1;
        display: none;
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
        self._no_providers = False
        self._error = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield RichLog(id="log", wrap=True, markup=True, highlight=True)
            yield Static(id="stream")
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
            agent, _, sysctx = build_agent(self.workdir)
            self._agent = agent
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
        log.write(Panel.fit(f"[bold blue]❯[/bold blue] {text}", border_style="blue"))  # noqa: RUF001

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
        try:
            await self._run_agent_streaming(log)
        except Exception as e:
            log.write(Panel.fit(f"[red]Error: {e}[/red]", border_style="red"))
        finally:
            self.query_one("#stream", Static).update("")

    async def _run_agent_streaming(self, log: RichLog) -> None:
        """Run the loop with live streaming: text deltas + tool cards."""
        from eaccode.llm.models import Message

        history = []
        for m in self.messages:
            if m["role"] == "user":
                history.append(Message.user(m["content"]))
            else:
                history.append(Message.assistant(m["content"]))

        stream_box = self.query_one("#stream", Static)
        stream_box.styles.display = "block"

        def on_text(delta: str) -> None:
            stream_box.update(stream_box.renderable + delta)

        def on_tool_call(tc: ToolCall) -> None:
            stream_box.update("")
            args = ", ".join(f"{k}={v}" for k, v in tc.arguments.items())
            log.write(Panel.fit(f"[cyan]⚙ {tc.name}({args})[/cyan]", border_style="cyan"))

        def on_tool_result(tc: ToolCall, result: ToolResult) -> None:
            style = "green" if not result.is_error else "red"
            icon = "✓" if not result.is_error else "✗"
            preview = result.content[:400]
            if len(result.content) > 400:
                preview += " …"
            log.write(
                Panel.fit(
                    f"[{style}]{icon} {tc.name}[/{style}] {preview}",
                    border_style=style,
                )
            )

        result = await self._agent.run_streaming(
            history,
            on_text_delta=on_text,
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
        )
        stream_box.styles.display = "none"
        log.write(result.final_text)
        self.messages.append({"role": "assistant", "content": result.final_text})


def run_repl(workdir: Path | None = None) -> None:
    EaccodeApp(workdir=workdir).run()
