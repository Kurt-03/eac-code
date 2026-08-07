"""Textual REPL (Task 7.1/7.3) — interactive chat with live streaming.

Designed like Claude Code / Hermes: a status header (model · mode · cwd),
clean message flow (user ">" prompt, assistant answer), compact one-line tool
cards, live text streaming, and a footer with key bindings.

Selection note: Textual owns the mouse, so the terminal's own text
selection is disabled while the app runs — use `/copy` to put the last
assistant answer on the Windows clipboard (clip.exe), or `/copy all`.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from rich.panel import Panel
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static

from eaccode.llm.models import ToolCall
from eaccode.memory.store import MemoryStore
from eaccode.tools.base import ToolResult
from eaccode.ui.commands import handle_command


class EaccodeApp(App):
    TITLE = "eaccode"
    SUB_TITLE = "autonomous coding agent"

    CSS = """
    Screen {
        background: $background;
    }
    #log {
        height: 1fr;
        border: none;
        padding: 1 2;
        background: $surface;
    }
    #stream {
        height: auto;
        max-height: 10;
        color: $text-muted;
        padding: 0 2 0 2;
        display: none;
    }
    #input {
        height: 3;
        border: round $accent;
        border-title-color: $accent;
        padding: 0 1;
        background: $surface;
    }
    #input:focus {
        border: round $primary;
    }
    """

    BINDINGS: ClassVar = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+y", "copy_last", "Copy last answer"),
    ]

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
        self._last_answer = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield RichLog(id="log", wrap=True, markup=True, highlight=False)
            yield Static(id="stream")
            yield Input(placeholder="Ask eaccode anything…  (/help for commands)", id="input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        self.query_one(Input).focus()  # typing starts immediately
        log.write("[dim]Welcome to eaccode — autonomous coding agent.[/dim]")
        log.write("[dim]Ask for code, files, commands, or reviews. "
                  "Type /help for commands.[/dim]\n")
        try:
            from eaccode.agent.factory import build_agent_async
            from eaccode.config.paths import EaccodePaths
            from eaccode.tools.mcp.client import connect_mcp_tools

            paths_cls = EaccodePaths
            self.run_worker(self._init_agent(build_agent_async, paths_cls,
                                             connect_mcp_tools, log), exclusive=True)
        except RuntimeError as e:
            self._no_providers = True
            self._error = str(e)
            log.write(Panel.fit(f"[red]{e}[/red]", border_style="red"))

    async def _init_agent(self, build_agent_async, paths_cls,
                          connect_mcp_tools, log) -> None:
        """Async init inside Textual's loop (asyncio.run is forbidden here)."""
        try:
            paths = paths_cls()
            mcp_tools, _mcp_mgr = await connect_mcp_tools(
                paths.config_dir / "mcp.yaml"
            )
            agent, _, sysctx = await build_agent_async(
                self.workdir, mcp_tools=mcp_tools
            )
        except Exception as e:
            self._no_providers = True
            self._error = str(e)
            log.write(Panel.fit(f"[red]{e}[/red]", border_style="red"))
            return
        self._agent = agent
        self.memory_facts = sysctx.memory_facts
        if mcp_tools:
            log.write(f"[dim]mcp: {len(mcp_tools)} external tool(s) loaded[/dim]")
        if sysctx.memory_facts:
            log.write("[dim]memory:[/dim]")
            for f in sysctx.memory_facts:
                log.write(f"[dim]  • {f}[/dim]")
        log.write("\n[dim]Ready. Ask away — the agent has read, write, bash, "
                  "grep, web, todo, and skill tools.[/dim]\n")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        log = self.query_one("#log", RichLog)
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        log.write(Panel.fit(f"[bold blue]❯[/bold blue] {text}",  # noqa: RUF001
                            border_style="blue", title="you"))

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
        stream_box.update("[dim]… working[/dim]")
        self._stream_text = ""

        def on_text(delta: str) -> None:
            self._stream_text += delta
            stream_box.update(f"[dim]{self._stream_text}[/dim]")

        def on_tool_call(tc: ToolCall) -> None:
            stream_box.update("")
            self._stream_text = ""
            args = ", ".join(f"{k}={v}" for k, v in tc.arguments.items())
            log.write(
                Panel.fit(
                    f"[cyan]⚙ {tc.name}[/cyan] [dim]{args}[/dim]",
                    border_style="cyan",
                    title="tool",
                )
            )

        def on_tool_result(tc: ToolCall, result: ToolResult) -> None:
            if result.is_error:
                preview = result.content[:300]
                log.write(
                    Panel.fit(
                        f"[red]✗ {tc.name}[/red]\n[dim]{preview}[/dim]",
                        border_style="red",
                        title="failed",
                    )
                )
            else:
                first_line = result.content.splitlines()[0] if result.content else ""
                more = len(result.content.splitlines()) - 1
                extra = f" [dim](+{more} lines)[/dim]" if more > 0 else ""
                log.write(
                    Panel.fit(
                        f"[green]✓ {tc.name}[/green] [dim]{first_line[:150]}[/dim]{extra}",
                        border_style="green",
                        title="done",
                    )
                )

        result = await self._agent.run_streaming(
            history,
            on_text_delta=on_text,
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
        )
        stream_box.styles.display = "none"
        self._last_answer = result.final_text
        log.write(f"[cyan]eaccode[/cyan]\n{result.final_text}")
        self.messages.append({"role": "assistant", "content": result.final_text})

    def action_copy_last(self) -> None:
        """Copy the last assistant answer to the Windows clipboard."""
        if not self._last_answer:
            self.query_one("#log", RichLog).write(
                "[dim]Nothing to copy yet.[/dim]"
            )
            return
        import subprocess

        try:
            subprocess.run(
                ["clip"], input=self._last_answer.encode("utf-16-le"),
                check=False,
            )
            self.query_one("#log", RichLog).write(
                "[dim]✓ Last answer copied to clipboard (paste with Ctrl+V)[/dim]"
            )
        except Exception as e:
            self.query_one("#log", RichLog).write(
                f"[red]✗ Clipboard failed: {e}[/red]"
            )


def run_repl(workdir: Path | None = None) -> None:
    EaccodeApp(workdir=workdir).run()
