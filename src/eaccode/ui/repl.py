"""Textual REPL (Task 7.1/7.3) — interactive chat with live streaming.

Designed like Claude Code / Hermes: a status header (model · mode · cwd),
clean message flow (user ">" prompt, assistant answer), compact one-line tool
cards, live text streaming, and a footer with key bindings.

Selection note: Textual owns the mouse, so the terminal's own text
selection is disabled while the app runs — use `/copy` to put the last
assistant answer on the Windows clipboard (clip.exe), or `/copy all`.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, RichLog, Static

from eaccode.llm.client import TokenUsage
from eaccode.llm.models import ToolCall
from eaccode.memory.store import MemoryStore
from eaccode.sessions.store import SessionStore  # D.2: session persistence
from eaccode.tools.base import ToolResult
from eaccode.ui.commands import handle_command
from eaccode.ui.suggester import SlashCommandSuggester


class EaccodeApp(App):
    TITLE = "eaccode"
    SUB_TITLE = ""

    # v0.4.0 (Phase A): no Header, no Footer, no border boxes, no
    # surface background. The Log sits on the terminal's default,
    # the Input has a thin separator above it, the Status bar lives
    # below the Input as a plain Static.
    CSS = """
    Screen {
        background: $background;
    }
    #log {
        height: 1fr;
        border: none;
        padding: 0 1;
        background: $background;
    }
    #input {
        height: 1;
        border: none;
        padding: 0 1;
        background: $background;
    }
    #status {
        height: 1;
        dock: bottom;
        padding: 0 1;
        color: $text-muted;
        background: $background;
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
        self._usage_by_model: dict[str, TokenUsage] = {}  # J.6: per-model
        self._install_plugin_commands()
        # P0.9: persistent allowlist + per-pattern approval counters.
        from eaccode.permissions.allowlist import AllowlistStore

        self._allowlist = AllowlistStore()
        self._approval_counts: dict[str, int] = {}
        # B.4: pending approval registry (resolvable via /approve /deny).
        from eaccode.permissions.approvals import ApprovalRegistry

        self._approvals = ApprovalRegistry()
        # C.1: background-review scheduler (settings.review_every_turns).
        from eaccode.agent.review_scheduler import ReviewScheduler
        from eaccode.config.paths import EaccodePaths
        from eaccode.config.settings import Settings

        _settings = Settings.load(EaccodePaths().settings_file)
        self._review_scheduler = ReviewScheduler(_settings.review_every_turns)
        # D.2/D.6: session persistence — id, store, save on exit.
        self._session_id: str = ""
        self._session_title: str = ""
        self._session_lock: Path | None = None
        self._session_store: SessionStore | None = None
        self._save_sessions = _settings.save_sessions
        # F.27/F.28: emergency-stop flag shared with the agent loop.
        import asyncio

        self._estop_flag = asyncio.Event()
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
        # v0.4.0 (Phase A): drop Header / Footer. Flat log + input + status.
        # Log keeps Rich markup ([dim], [green], …) for subtle styling —
        # only the surrounding Boxen are gone.
        with Vertical():
            yield RichLog(id="log", wrap=True, markup=True, highlight=False)
            yield Input(
                placeholder="›  ask eaccode…  (/ for commands)",
                id="input",
                suggester=self._suggester,
            )
            yield Static(id="status")

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
        # A.9: memory nudge renders into the log.
        if agent.config.memory_nudge_every_turns > 0:
            agent.config.on_nudge = lambda msg: log.write(f"[dim]{msg}[/dim]")
        # P0.10: session_start hook (fire-and-forget, advisory).
        if agent.config.hooks_dir is not None:
            from eaccode.hooks.runner import run_hooks

            await asyncio.to_thread(
                run_hooks, "session_start", self.workdir,
                hooks_dir=agent.config.hooks_dir,
            )
        # Phase B.1: wire the in-REPL permission modal into the loop.
        agent.config.ask_async = self._ask_permission_async
        # P0.8: the `P` approve level pauses the session; /resume unpauses.
        if agent.config.pause_flag is None:
            from eaccode.permissions.session import PauseFlag

            agent.config.pause_flag = PauseFlag()
        self._pause_flag = agent.config.pause_flag
        # F.27/F.28: estop flag (set by Ctrl+C while busy).
        agent.config.estop_flag = self._estop_flag
        # P0.9: wire the persistent allowlist into the policy engine.
        agent.policy.allowlist = self._allowlist
        self.memory_facts = sysctx.memory_facts
        # D.2/D.6/D.8: start the persisted session (id + lease).
        self._start_session(paths_cls)
        if mcp_tools:
            log.write(f"[dim]mcp: {len(mcp_tools)} external tool(s) loaded[/dim]")
        if sysctx.memory_facts:
            log.write("[dim]memory:[/dim]")
            for f in sysctx.memory_facts:
                log.write(f"[dim]  • {f}[/dim]")
        log.write("\n[dim]Ready. Ask away — the agent has read, write, bash, "
                  "grep, web, todo, and skill tools.[/dim]\n")
        # J.4: onboarding hints for fresh sessions (first run of the app).
        if not self.messages and not getattr(self, "_onboarding_done", False):
            self._onboarding_done = True
            log.write("[dim]Hints: /help lists commands · @file:path injects "
                      "files · /mode safeAuto auto-approves safe bash[/dim]")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        log = self.query_one("#log", RichLog)
        # J.35: input sanitization — strip control characters, trim.
        text = "".join(ch for ch in event.value if ch >= " " or ch == "\t")
        text = text.strip()
        if not text:
            return
        event.input.value = ""
        log.write(f"› {text}\n")  # v0.4.0: flat user marker, no Panel

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
            # v0.4.0: spinner is now part of the Log — hide via the
            # `_hide_spinner` path called from on_text / on_tool_result.

    def _ask_permission_async(self, tool_name: str, arguments: dict, question: str) -> object:
        """Push the permission modal; return a Future the loop awaits (B.1)."""
        import asyncio

        from eaccode.ui.permission_modal import PermissionModal

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        # H.1: redacted + canonicalized arguments for the permission modal.
        from eaccode.security.guards import display_arguments

        display_args = display_arguments(tool_name, arguments, self.workdir)
        modal = PermissionModal(tool_name, display_args, question,
                                resolve=future.set_result)
        self.push_screen(modal)
        # B.4: register the ask so /approve <id> / /deny <id> can resolve
        # it while the modal is open (or after the fact).
        self._approvals.register(tool_name, arguments, question, future)
        # P0.9: count approvals; after 3x of the same pattern suggest the
        # allowlist (one hint, then the counter resets).
        future.add_done_callback(
            lambda f: self._on_approval_resolved(tool_name, arguments, f)
        )
        return future

    def _on_approval_resolved(self, tool_name: str, arguments: dict, future) -> None:
        """P0.9 suggest-mode: after repeated approvals, offer /allow."""
        from eaccode.permissions.allowlist import suggest_pattern
        from eaccode.permissions.prompts import PermissionChoice

        try:
            choice = future.result()
        except Exception:
            return
        if choice not in (PermissionChoice.ALLOW_ONCE, PermissionChoice.ALLOW_ALWAYS):
            return
        pattern = suggest_pattern(tool_name, arguments)
        key = f"{tool_name}|{pattern}"
        count = self._approval_counts.get(key, 0) + 1
        self._approval_counts[key] = count
        if count >= 3:
            self._approval_counts[key] = 0  # one hint per pattern
            log = self.query_one("#log", RichLog)
            log.write(
                f"[dim][ i ] Approved {tool_name} {count}x — save it permanently "
                f"with /allow {tool_name} '{pattern}'[/dim]"
            )

    async def _run_agent_streaming(self, log: RichLog) -> None:
        """Run the loop with live streaming: text deltas + tool cards."""
        from eaccode.llm.models import Message

        history = []
        for m in self.messages:
            if m["role"] == "user":
                history.append(Message.user(m["content"]))
            else:
                history.append(Message.assistant(m["content"]))

        log = self.query_one("#log", RichLog)
        self._stream_text = ""
        self._reasoning_text = ""
        self._tool_starts: dict[str, float] = {}
        # v0.4.0 (Phase A): spinner writes a single line into the Log that
        # gets replaced on every tick (no separate #stream Static).
        self._spinner_line_idx = log.write("  ⠋")
        # C.4: single-writer fence — a new turn supersedes this stream.
        # claim_stream_writer stores the token on self (P0.6 Bug 1 fix).
        from eaccode.llm.stream_fence import claim_stream_writer, fence_delta

        claim_stream_writer(self)
        writer_token = self._stream_writer_token
        # B.4: animated spinner while the agent works (v0.4.0: ASCII cycle,
        # line already written into the Log by _run_agent_streaming above).
        self._spinner_idx = 0
        self._spinner_interval = self.set_interval(0.125, self._tick_spinner)
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
            if self._spinner_line_idx is not None:
                try:
                    log.lines.pop(self._spinner_line_idx)
                except Exception:
                    pass
                self._spinner_line_idx = None

        def on_text(delta: str) -> None:
            if fence_delta(self, writer_token, delta) is None:
                return  # stale stream — a newer turn owns the UI
            _hide_spinner()
            self._stream_text += delta
            self.query_one("#log", RichLog).write(f"    {self._stream_text}")

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
            self.query_one("#log", RichLog).write(
                f"[dim italic]{capped}{suffix}[/dim italic]\n"
                f"[dim]{self._stream_text}[/dim]"
            )

        def on_tool_call(tc: ToolCall) -> None:
            _hide_spinner()
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
        # v0.4.0: spinner is part of the Log now; nothing to hide here.
        self._last_answer = result.final_text
        log.write(f"[cyan]eaccode[/cyan]\n{result.final_text}")
        self.messages.append({"role": "assistant", "content": result.final_text})
        # C.1: background review when the turn window is reached.
        if self._review_scheduler.should_review(result.turns):
            self.run_worker(self._run_review_worker(log), exclusive=False)
        # D.2: persist the conversation (provenance-aware title).
        if self._session_title == "":
            from eaccode.sessions.titles import derive_title

            first_user = next(
                (m["content"] for m in self.messages
                 if m.get("role") == "user" and m.get("content")), ""
            )
            self._session_title = derive_title(first_user)
        self._save_session()
        # Status bar (Phase B.2): model · mode · tokens · cost · ctx%
        self._total_usage += result.usage
        # J.6: per-model spend breakdown (/cost).
        model_key = self._model_name or "default"
        per_model = self._usage_by_model.setdefault(model_key, TokenUsage())
        per_model.input_tokens += result.usage.input_tokens
        per_model.output_tokens += result.usage.output_tokens
        per_model.cost_usd += result.usage.cost_usd
        ctx_pct = self._context_pct()
        # v0.4.0 (Phase A.4): write the new status bar — drop sub_title.
        from eaccode.tui.status_bar import StatusBar

        self.query_one("#status", Static).update(StatusBar(
            model=self._model_name or "?",
            mode=self._mode_name or self._agent.policy.mode.value,
            context_pct=ctx_pct,
            cost_usd=self._total_usage.cost_usd,
        ).render())
        # F.20: collapsed reasoning summary + F.21: context guidance.
        if self._reasoning_text and not self._show_reasoning:
            from eaccode.agent.runtime_helpers import summarize_reasoning

            log.write(f"[dim italic]🧠 {summarize_reasoning(self._reasoning_text)}[/dim italic]")
        self._reasoning_text = ""
        if ctx_pct is not None and ctx_pct >= 60:
            log.write(f"[yellow]context at {ctx_pct}% — /compress frees tokens[/yellow]")

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

    async def _run_review_worker(self, log: RichLog) -> None:
        """C.2/C.3: run the whitelisted review; proposals enter the
        approval registry — applying them requires /approve."""
        import asyncio

        from eaccode.agent.background_review import run_review
        from eaccode.agent.factory import build_agent_async
        from eaccode.memory.markdown_store import MarkdownMemoryStore
        from eaccode.memory.store import MemoryStore

        agent = getattr(self, "_agent", None)
        if agent is None:
            return
        # Compact session summary: last few user/assistant texts.
        summary_lines = [
            m["content"][:400] for m in self.messages[-6:]
            if m.get("content")
        ]
        if not summary_lines:
            return
        log.write("[dim]background review running…[/dim]")
        result = await run_review(
            build_agent_async, self.workdir, "\n".join(summary_lines)
        )
        if result.empty:
            log.write("[dim]review: nothing to propose.[/dim]")
            return
        store = MarkdownMemoryStore(self._md_memory_dir())
        hash_ = MemoryStore.project_hash(self.workdir)
        ids: list[int] = []
        for fact in result.facts:
            future: asyncio.Future = asyncio.get_running_loop().create_future()
            approval_id = self._approvals.register(
                "memory_remember",
                {"fact": fact},
                f"review: save fact {fact[:50]!r}",
                future,
                on_approve=lambda f=fact: store.add_fact("memory", f, hash_),
            )
            ids.append(approval_id)
        log.write(
            f"[dim]review: {len(result.facts)} fact(s) proposed — "
            f"/approve {' '.join(f'#{i}' for i in ids)} to save "
            "(/deny to discard).[/dim]"
        )
        if result.skills:
            log.write("[dim]review: skill suggestions (not applied): "
                      + "; ".join(result.skills) + "[/dim]")

    def _start_session(self, paths_cls) -> None:
        """D.2/D.6/D.8: create session id, store, lease (idempotent)."""
        if self._session_id:
            return
        import uuid

        paths = paths_cls()
        self._session_id = str(uuid.uuid4())
        self._session_store = SessionStore(paths.sessions_dir / "sessions.db")
        from eaccode.sessions.leases import acquire_lease, cleanup_stale_leases

        cleanup_stale_leases(paths.sessions_dir)  # crashed-session cleanup
        self._session_lock = acquire_lease(paths.sessions_dir, self._session_id)

    def _save_session(self, upgrade_title: bool = False) -> None:
        """D.2/D.6: persist messages + metadata (provenance-aware title)."""
        if not self._save_sessions or self._session_store is None:
            return
        if not self.messages:
            return
        import asyncio

        from eaccode.llm.models import Message as LlmMessage

        msgs = []
        for m in self.messages:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                msgs.append(LlmMessage.user(m["content"])
                            if m["role"] == "user"
                            else LlmMessage.assistant(m["content"]))
        if not msgs:
            return
        title = self._session_title or ""
        provenance = "user" if self._session_title else "derived"
        metadata = {
            "cwd": str(self.workdir),
            "provider": self._model_name or "",
            "model": self._model_name or "",
        }
        try:
            asyncio.get_running_loop()
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            from eaccode.agent.thread_silence import thread_silenced

            with thread_silenced():  # F.29: background worker stays quiet
                self._save_task = asyncio.create_task(
                    self._session_store.save(
                        title, msgs, metadata,
                        session_id=self._session_id, provenance=provenance,
                    )
                )
        else:  # pragma: no cover - headless contexts
            asyncio.run(
                self._session_store.save(
                    title, msgs, metadata,
                    session_id=self._session_id, provenance=provenance,
                )
            )

    def _release_session(self) -> None:
        """D.8: drop the lease + final save on exit."""
        if self._session_lock is not None:
            from eaccode.sessions.leases import release_lease

            release_lease(self._session_lock)
            self._session_lock = None

    def _md_memory_dir(self):
        """Memory dir used by the review worker (matches commands.py)."""
        from eaccode.config.paths import EaccodePaths

        return EaccodePaths().memory_dir

    def _spinner_frame(self) -> str:
        """Next ASCII spinner frame (Phase A.2: v0.4.0)."""
        from eaccode.tui.spinner import Spinner as _Spinner

        # Use a small standalone instance so the spinner's index advances
        # independently of the legacy _spinner_idx counter.
        spinner = _Spinner(interval=0.125)
        spinner.tick()
        return spinner.frame()

    def _tick_spinner(self) -> None:
        """v0.4.0 (Phase A.2): replace the spinner line in the Log."""
        from eaccode.tui.spinner import Spinner as _Spinner

        if not self._busy or self._spinner_line_idx is None:
            return
        self._spinner = getattr(self, "_spinner", _Spinner(interval=0.125))
        self._spinner.tick()
        try:
            log = self.query_one("#log", RichLog)
            if self._spinner_line_idx < len(log.lines):
                log.lines[self._spinner_line_idx]._renderable = (
                    f"  {self._spinner.frame()}"
                )
                log.refresh()
        except Exception:
            pass

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
            # F.27/F.28: estop flag — the loop stops executing tools.
            flag = getattr(self, "_estop_flag", None)
            if flag is not None:
                flag.set()
            self._current_task.cancel()
            self.query_one("#log", RichLog).write(
                "[yellow]⏹ interrupted by user[/yellow]"
            )
            self._busy = False
            return
        # P0.10: session_end hook (fire-and-forget — the app is exiting).
        self._run_session_end_hook()
        # C.4: cancel running background delegations on exit.
        from eaccode.tools.builtin.delegate import cancel_all_background

        cancel_all_background()
        # G.2/G.3: kill parked processes + daemons on exit.
        from eaccode.tools.process_registry import kill_all

        kill_all()
        # D.2/D.8: final save + lease release.
        self._save_session()
        self._release_session()
        self.exit()

    def _run_session_end_hook(self) -> None:
        """P0.10: run session_end.sh off the event loop (daemon thread)."""
        agent = getattr(self, "_agent", None)
        if agent is None or agent.config.hooks_dir is None:
            return
        import threading

        from eaccode.hooks.runner import run_hooks

        hooks_dir = agent.config.hooks_dir
        workdir = agent.config.workdir

        def _fire() -> None:
            from contextlib import suppress

            with suppress(Exception):
                run_hooks("session_end", workdir, hooks_dir=hooks_dir)

        threading.Thread(target=_fire, daemon=True).start()

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
                f"✓ model switched to {name}"
            )
            # v0.4.0: refresh the status bar widget instead of sub_title.
            self._refresh_status_bar()
        except Exception as e:
            self.query_one("#log", RichLog).write(
                f"✗ model switch failed: {e}"
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
