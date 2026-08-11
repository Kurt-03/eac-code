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

from eaccode.llm.client import TokenUsage
from eaccode.llm.models import ToolCall
from eaccode.memory.store import MemoryStore
from eaccode.tools.base import ToolResult
from eaccode.ui.commands import handle_command
from eaccode.ui.suggester import SlashCommandSuggester


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
        Binding("ctrl+c", "quit_or_cancel", "Quit/Cancel"),
        Binding("ctrl+y", "copy_last", "Copy last answer"),
        Binding("ctrl+k", "open_palette", "Command palette"),
    ]

    def __init__(self, workdir: Path | None = None,
                 initial_messages: list | None = None) -> None:
        super().__init__()
        self.workdir = (workdir or Path.cwd()).resolve()
        self.messages: list = initial_messages or []
        self.last_usage = None
        self.memory_facts: list[str] = []
        self.memory_store: MemoryStore | None = None
        self.loaded_skills: list[str] = []
        self._session_touched: set[str] = set()
        self._agent = None
        self._no_providers = False
        self._error = ""
        self._last_answer = ""
        self._last_prompt = ""
        self.verbose_level = "new"  # tool display: off|new|all|verbose
        self._busy = False
        self._current_task = None
        self._model_name = ""
        self._mode_name = ""
        self._show_reasoning = False
        self._total_usage = TokenUsage()
        self._install_plugin_commands()
        self._suggester = SlashCommandSuggester(cwd=self.workdir)
        self._spinner_interval = None

    def _install_plugin_commands(self) -> None:
        """Phase I.12: wire context-engine plugin slash commands before the
        suggester is built, so completion/help/palette see them."""
        from eaccode.config.paths import EaccodePaths
        from eaccode.context.engine import get_engine
        from eaccode.ui.commands import install_plugin_commands

        install_plugin_commands(get_engine(EaccodePaths().plugins_dir).slash_specs())

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield RichLog(id="log", wrap=True, markup=True, highlight=False)
            yield Static(id="stream")
            yield Input(
                placeholder="Ask eaccode anything…  (/help for commands)",
                id="input",
                suggester=self._suggester,  # Phase F.2: slash/@/path completion
            )
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
            from eaccode.ui.messages import write_warn

            log.write(write_warn(str(e)))

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
            from eaccode.ui.messages import write_warn

            log.write(write_warn(str(e)))
            return
        self._agent = agent
        # Phase B.1: wire the in-REPL permission modal into the loop.
        agent.config.ask_async = self._ask_permission_async
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
            from eaccode.ui.messages import write_warn

            log.write(write_warn(self._error))
            return

        self.messages.append({"role": "user", "content": text})
        self._last_prompt = text
        self._busy = True
        try:
            import asyncio

            self._current_task = asyncio.create_task(self._run_agent_streaming(log))
            await self._current_task
        except asyncio.CancelledError:
            log.write("[yellow]⏹ run cancelled[/yellow]")
        except Exception as e:
            from eaccode.ui.messages import write_error

            log.write(write_error(f"Agent loop crashed: {e}"))
        finally:
            self._busy = False
            self._current_task = None
            self.query_one("#stream", Static).update("")

    def _ask_permission_async(self, tool_name: str, arguments: dict, question: str) -> object:
        """Push the permission modal; return a Future the loop awaits (B.1)."""
        import asyncio

        from eaccode.ui.permission_modal import PermissionModal

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        modal = PermissionModal(tool_name, arguments, question, resolve=future.set_result)
        self.push_screen(modal)
        return future

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
        self._stream_text = ""
        self._reasoning_text = ""
        self._tool_starts: dict[str, float] = {}
        # C.4: single-writer fence — a new turn supersedes this stream.
        # claim_stream_writer stores the token on self (P0.6 Bug 1 fix).
        from eaccode.llm.stream_fence import claim_stream_writer, fence_delta

        claim_stream_writer(self)
        writer_token = self._stream_writer_token
        # B.4: animated spinner while the agent works (Braille cycle).
        self._spinner_idx = 0
        self._spinner_interval = self.set_interval(0.125, self._tick_spinner)
        stream_box.update(self._spinner_frame())
        from eaccode.ui.preview import (
            CHEVRON,
            VerboseLevel,
            build_call_card,
            build_tool_label,
        )

        def _hide_spinner() -> None:
            if self._spinner_interval is not None:
                self._spinner_interval.stop()
                self._spinner_interval = None

        def on_text(delta: str) -> None:
            if fence_delta(self, writer_token, delta) is None:
                return  # stale stream — a newer turn owns the UI
            _hide_spinner()
            self._stream_text += delta
            stream_box.update(f"[dim]{self._stream_text}[/dim]")

        def on_reasoning_delta(delta: str) -> None:
            """Accumulate reasoning; render collapsed above the answer (B.3).

            MiniMax-M3 spends 1k-3k tokens thinking on hard prompts — the
            display is capped at 2 KB by default and only expands with
            `/reasoning on` (or `show-full`).
            """
            if fence_delta(self, writer_token, delta) is None:
                return  # stale stream
            self._reasoning_text += delta
            if not self._show_reasoning:
                return  # collapsed: don't paint, just accumulate
            capped = self._reasoning_text[:2000]
            suffix = "…" if len(self._reasoning_text) > 2000 else ""
            stream_box.update(
                f"[dim italic]{capped}{suffix}[/dim italic]\n[dim]{self._stream_text}[/dim]"
            )

        def on_tool_call(tc: ToolCall) -> None:
            _hide_spinner()
            stream_box.update("")
            self._stream_text = ""
            import time

            self._tool_starts[tc.id] = time.monotonic()
            if VerboseLevel.show_start(self.verbose_level):
                # Phase H.6: friendly verb label ("Running pytest…") instead
                # of the raw call expression when a verb is known.
                label = build_tool_label(tc.name, tc.arguments)
                if label:
                    log.write(f"[dim]{CHEVRON} {label}[/dim]")
                else:
                    card = build_call_card(
                        tc.name, tc.arguments,
                        full_args=VerboseLevel.show_full_args(self.verbose_level),
                    )
                    log.write(f"[dim]{CHEVRON} {card.call}[/dim]")

        def on_tool_result(tc: ToolCall, result: ToolResult) -> None:
            import time

            duration = None
            start = self._tool_starts.pop(tc.id, None)
            if start is not None:
                duration = time.monotonic() - start
            if not VerboseLevel.show_result(self.verbose_level, result.is_error):
                return
            card = build_call_card(
                tc.name, tc.arguments, result=result.content,
                is_error=result.is_error, duration_s=duration,
                result_max=140 if self.verbose_level == VerboseLevel.VERBOSE else 90,
                full_args=VerboseLevel.show_full_args(self.verbose_level),
            )
            mark = "✗" if result.is_error else "✓"
            style = "red" if result.is_error else "green"
            duration_txt = f" · {duration:.1f}s" if duration is not None else ""
            preview_txt = f" {card.result_preview}" if card.result_preview else ""
            log.write(f"  [{style}]{mark}[/{style}] {card.name}{duration_txt}{preview_txt}")
            # Phase B.7: multi-line result preview with collapse.
            if card.result_lines and self.verbose_level in (
                VerboseLevel.ALL, VerboseLevel.VERBOSE,
            ):
                for line in card.result_lines:
                    log.write(f"    [dim]{line}[/dim]")
                if card.collapsed:
                    log.write(f"    [dim]… ({card.more_lines} more lines — "
                              f"/verbose verbose to expand)[/dim]")

        result = await self._agent.run_streaming(
            history,
            on_text_delta=on_text,
            on_reasoning_delta=on_reasoning_delta,
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
        )
        stream_box.styles.display = "none"
        self._last_answer = result.final_text
        log.write(f"[cyan]eaccode[/cyan]\n{result.final_text}")
        self.messages.append({"role": "assistant", "content": result.final_text})
        # Status bar (Phase B.2): model · mode · tokens · cost · ctx%
        self._total_usage += result.usage
        ctx_pct = self._context_pct()
        ctx_txt = f" · {ctx_pct}%" if ctx_pct is not None else ""
        self.sub_title = (
            f"{self._model_name or '?'} · {self._mode_name or self._agent.policy.mode.value} · "
            f"{self._total_usage.input_tokens + self._total_usage.output_tokens} tok · "
            f"${self._total_usage.cost_usd:.4f}{ctx_txt}"
        )

    def _context_pct(self) -> int | None:
        """Context-window usage % for the status bar (Phase B.5)."""
        from eaccode.llm.tokens import count_message_tokens, model_context_window

        if not self.messages:
            return None
        model = self._model_name or "default"
        try:
            window = model_context_window(model)
            used = count_message_tokens(self.messages, model)
        except Exception:
            return None
        return min(100, max(1, round(used * 100 / window)))

    def _spinner_frame(self) -> str:
        """Next Braille spinner frame (Phase B.4)."""
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        frame = frames[self._spinner_idx % len(frames)]
        self._spinner_idx += 1
        return f"[dim]{frame} working…[/dim]"

    def _tick_spinner(self) -> None:
        """Textual interval callback: repaint the spinner frame."""
        if self._busy:
            stream = self.query_one("#stream", Static)
            if stream.styles.display != "none":
                stream.update(self._spinner_frame())

    def action_open_palette(self) -> None:
        """Ctrl+K: open the filterable command palette (Phase F.3)."""
        from eaccode.ui.command_palette import CommandPalette

        def run(name: str) -> None:
            log = self.query_one("#log", RichLog)
            result = handle_command(name, self)
            if result.message:
                log.write(result.message)
            if result.should_exit:
                self.exit()

        self.push_screen(CommandPalette(on_run=run))

    def _toggle_skill(self, name: str, enable: bool) -> None:
        """Session skill toggle for /skills (Phase G.6)."""
        if enable:
            if name not in self.loaded_skills:
                self.loaded_skills.append(name)
        else:
            if name in self.loaded_skills:
                self.loaded_skills.remove(name)

    def action_quit_or_cancel(self) -> None:
        """Ctrl+C: cancel a running agent, otherwise quit the app."""
        if self._busy and self._current_task:
            self._current_task.cancel()
            self.query_one("#log", RichLog).write(
                "[yellow]⏹ interrupted by user[/yellow]"
            )
            self._busy = False
            return
        self.exit()

    def _switch_model(self, name: str) -> str:
        """/model: rebuild the agent with another provider/model (Phase B.4)."""
        from eaccode.agent.factory import build_agent_async

        try:

            self.run_worker(
                self._switch_model_worker(name, build_agent_async), exclusive=True
            )
            return f"Switching model to '{name}'..."
        except Exception as e:
            return f"Model switch failed: {e}"

    async def _switch_model_worker(self, name: str, build_agent_async) -> None:
        try:
            agent, _client, _ = await build_agent_async(self.workdir, model=name)
            self._agent = agent
            self._model_name = name
            self.query_one("#log", RichLog).write(
                f"[green]✓ model switched to {name}[/green]"
            )
            self.sub_title = f"{name} · {self._mode_name or agent.policy.mode.value}"
        except Exception as e:
            self.query_one("#log", RichLog).write(
                f"[red]✗ model switch failed: {e}[/red]"
            )

    def _retry_last(self) -> str:
        """/retry: re-run the last user prompt (Phase B.3)."""
        import asyncio

        self._busy = True
        log = self.query_one("#log", RichLog)

        async def _run() -> None:
            try:
                self._current_task = asyncio.current_task()
                await self._run_agent_streaming(log)
            except asyncio.CancelledError:
                log.write("[yellow]⏹ run cancelled[/yellow]")
            except Exception as e:
                from eaccode.ui.messages import write_error

                log.write(write_error(f"Agent loop crashed: {e}"))
            finally:
                self._busy = False
                self._current_task = None

        self.run_worker(_run(), exclusive=True)
        return f"Retrying: {self._last_prompt}"

    def action_copy_last(self) -> None:
        """Copy the last assistant answer to the system clipboard (G.4)."""
        if not self._last_answer:
            self.query_one("#log", RichLog).write(
                "[dim]Nothing to copy yet.[/dim]"
            )
            return
        from eaccode.ui.clipboard import write_clipboard_text

        try:
            if write_clipboard_text(self._last_answer):
                self.query_one("#log", RichLog).write(
                    "[dim]✓ Last answer copied to clipboard (paste with Ctrl+V)[/dim]"
                )
            else:
                self.query_one("#log", RichLog).write(
                    "[dim]✗ No clipboard tool available on this platform "
                    "(need wl-copy/xclip/xsel on Linux).[/dim]"
                )
        except Exception as e:
            self.query_one("#log", RichLog).write(
                f"[red]✗ Clipboard failed: {e}[/red]"
            )


def run_repl(workdir: Path | None = None, initial_messages: list | None = None) -> None:
    EaccodeApp(workdir=workdir, initial_messages=initial_messages).run()
