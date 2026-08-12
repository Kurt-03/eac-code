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
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, RichLog, Static

from eaccode.llm.client import TokenUsage
from eaccode.llm.models import ToolCall
from eaccode.memory.store import MemoryStore
from eaccode.sessions.store import SessionStore  # D.2: session persistence
from eaccode.tools.base import ToolResult
from eaccode.ui.commands import handle_command


class PermissionAwareInput(Input):
    """Input that hands y/s/a/n/p/Esc to the app while a permission is pending.

    ``Input._on_key`` is async in Textual 8 and stops printable keys to
    insert them as text — which is exactly why bare ``App.on_key`` never
    saw the permission letters (v0.4.0.x regression). This subclass
    checks the app's pending ask first and resolves it instead of
    inserting the character; otherwise it must ``await`` the base
    handler (a sync call would drop the insert coroutine).

    v0.0.1: the **s** key adds the ALLOW_SESSION quick-pick (session-only
    remember — not persisted to allowlist.json).

    I2 (audit): up/down also navigate the prompt history when the app
    has one (Hermes' useInputHistory behaviour).
    """

    async def _on_key(self, event) -> None:
        app = self.app
        if getattr(app, "_pending_permission", None):
            key = event.key.lower()
            if key in ("y", "s", "a", "n", "p", "escape"):
                app._resolve_pending_permission("n" if key == "escape" else key)
                event.stop()
                event.prevent_default()
                return
        history = getattr(app, "_input_history", [])
        if history:
            key = event.key.lower()
            if key == "up":
                app._history_navigate(-1)
                event.stop()
                event.prevent_default()
                return
            if key == "down":
                app._history_navigate(1)
                event.stop()
                event.prevent_default()
                return
        await super()._on_key(event)


class EaccodeApp(App):
    TITLE = "eaccode"
    SUB_TITLE = ""

    # Hermes-style chrome (v0.5.0): transcript on the terminal's own
    # background, a thin rule under the composer, and a status rule at
    # the very bottom. No boxes, no header/footer widgets.
    CSS = """
    Screen {
        background: $background;
    }
    #transcript {
        height: 1fr;
        border: none;
        padding: 0 1 0 1;
        background: $background;
    }
    #overlay {
        height: auto;
        max-height: 10;
        border: none;
        padding: 0 1 0 1;
        color: $text-muted;
    }
    #prompt-glyph {
        width: 3;
        padding: 0 1 0 1;
        color: $accent;
        content-align: right middle;
    }
    #composer-rule {
        height: 1;
        border: none;
        padding: 0 1;
        color: $border;
        background: $background;
    }
    #composer {
        height: 1;
        border: none;
        padding: 0 1 0 0;
        background: $background;
    }
    #status-rule {
        height: 1;
        border: none;
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
        # I2 (audit): prompt history (up/down), Hermes-style.
        self._input_history: list[str] = []
        self._history_idx: int | None = None
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
        self._spinner_interval = None
        # v0.5.0: Hermes-style slash overlay (fuzzy-ranked).
        from eaccode.tui.slash_overlay import SlashOverlay

        self._overlay = SlashOverlay()
        from eaccode.tui.theme import DEFAULT_THEME

        self.skin = DEFAULT_THEME

    def _install_plugin_commands(self) -> None:
        """Phase I.12: wire context-engine plugin slash commands before the
        suggester is built, so completion/help/palette see them."""
        from eaccode.config.paths import EaccodePaths
        from eaccode.context.engine import get_engine
        from eaccode.ui.commands import install_plugin_commands

        install_plugin_commands(get_engine(EaccodePaths().plugins_dir).slash_specs())

    def compose(self) -> ComposeResult:
        # v0.5.0 (Hermes-style): transcript + slash overlay + composer
        # (with the prompt glyph prefix) + status rule. No Header/Footer.
        # v0.0.1: a thin rule line between transcript and composer makes
        # the layout read as a clean column (no box, no border).
        with Vertical():
            yield RichLog(id="transcript", wrap=True, markup=True,
                          highlight=False)
            yield Static(id="overlay")
            yield Static("─" * 80, id="composer-rule")
            with Horizontal(id="composer-row"):
                yield Static(self.skin.brand.prompt, id="prompt-glyph")
                # I5 (audit): no inline ghost suggester — the fuzzy
                # slash overlay is the only completion UI.
                yield PermissionAwareInput(
                    placeholder="ask eaccode…  (/ for commands)",
                    id="input",
                )
            yield Static(id="status-rule")

    def on_mount(self) -> None:
        log = self.query_one("#transcript", RichLog)
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
        # B9 (audit): the status rule showed '—' because the model name
        # was never read off the built agent.
        client_model = getattr(getattr(agent, "client", None),
                               "default_model", None)
        if client_model:
            self._model_name = client_model
        self._refresh_status_rule()
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

    def on_input_changed(self, event) -> None:
        """v0.5.0: update the Hermes-style fuzzy slash overlay."""
        text = event.value
        self._overlay.update(text)
        overlay = self.query_one("#overlay", Static)
        lines = self._overlay.render_lines()
        overlay.update("\n".join(lines) if lines else "")

    def _composer_insert(self, value: str) -> None:
        """Insert *value* into the composer (Tab-completion)."""
        try:
            inp = self.query_one("#input", Input)
            inp.value = value
            inp.focus()
        except Exception:
            pass

    def _remember_prompt(self, text: str) -> None:
        """Push a submitted prompt onto the history (I2, Hermes-style)."""
        if not text or text.startswith("/"):
            return
        if self._input_history and self._input_history[-1] == text:
            return
        self._input_history.append(text)
        del self._input_history[:-50]  # cap
        self._history_idx = None

    def _history_navigate(self, delta: int) -> None:
        """Move through the prompt history; up/down (I2)."""
        if not self._input_history:
            return
        try:
            inp = self.query_one("#input", Input)
        except Exception:
            return
        if self._history_idx is None:
            self._history_idx = len(self._input_history) - 1 if delta < 0 \
                else len(self._input_history)
        else:
            self._history_idx += delta
        if self._history_idx < 0 or self._history_idx >= len(self._input_history):
            self._history_idx = None
            inp.value = ""
            return
        inp.value = self._input_history[self._history_idx]

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        log = self.query_one("#transcript", RichLog)
        # J.35: input sanitization — strip control characters, trim.
        text = "".join(ch for ch in event.value if ch >= " " or ch == "\t")
        text = text.strip()
        if not text:
            return
        event.input.value = ""
        # v0.5.0: Hermes-style user line — prompt glyph in the gutter.
        # B3 (audit): escape user text — brackets must survive markup.
        from rich.markup import escape as _esc

        log.write(f"[bold cyan]❯[/bold cyan] {_esc(text)}\n")

        if text.startswith("/"):
            # I4 (audit): Enter picks the highlighted overlay entry
            # instead of sending the raw typed text.
            if self._overlay.items:
                current = self._overlay.current()
                if current is not None:
                    typed_cmd = text.split()[0]
                    if typed_cmd != f"/{current['name']}":
                        text = f"/{current['name']}"
            # A2 (audit): a failing slash command must never take down
            # the whole TUI — log a red line instead.
            try:
                result = handle_command(text, self)
            except Exception as e:
                from eaccode.ui.commands import CommandResult

                result = CommandResult(message=f"✗ command error: {e}")
            if result.message:
                log.write(result.message)
            if result.should_exit:
                self.exit()
            return

        if self._no_providers:
            from eaccode.ui.messages import write_warn

            log.write(write_warn(self._error))
            return

        if self._busy:
            log.write("[dim]still working — wait for the turn to finish, "
                      "or press Ctrl+C[/dim]")
            return

        # G9 (audit): if the agent build failed at startup, say so
        # instead of letting run_streaming crash on None.
        if self._agent is None:
            from eaccode.ui.messages import write_error

            log.write(write_error("Agent not ready — check provider "
                                  "setup (eaccode doctor)"))
            return

        self.messages.append({"role": "user", "content": text})
        self._last_prompt = text
        self._remember_prompt(text)
        self._overlay.update("")  # close the menu after the submit
        self._busy = True
        # v0.5.2 (CRITICAL): do NOT await the turn inside the event
        # handler. Textual 8's message pump queues every key event while
        # a handler is awaited, so permission keys (y/a/n/p/Esc) never
        # reached the app while the agent was streaming — the "hängt
        # einfach" bug since v0.3.0. Fire-and-forget: the handler
        # returns immediately, the agent loop runs as its own task, and
        # key events keep flowing.
        import asyncio

        self._current_task = asyncio.create_task(self._run_agent_streaming(log))

        def _on_turn_done(task: asyncio.Task) -> None:
            try:
                task.result()  # re-raise to log the failure
            except asyncio.CancelledError:
                log.write("[yellow]⏹ run cancelled[/yellow]")
            except Exception as e:
                from eaccode.ui.messages import write_error

                log.write(write_error(f"Agent loop crashed: {e}"))
            finally:
                self._busy = False
                self._current_task = None

        self._current_task.add_done_callback(_on_turn_done)

    def _ask_permission_async(self, tool_name: str, arguments: dict, question: str) -> object:
        """v0.4.0 (Phase B): inline permission question in the Log stream.

        We write the prompt via ``render_permission_prompt`` into the Log,
        arm a key listener (y/a/n/p/Esc), and return a Future the loop
        awaits. ``/approve <id>`` and ``/deny <id>`` still work because
        the ApprovalRegistry is fed the same Future.
        """
        import asyncio

        from eaccode.security.guards import display_arguments
        from eaccode.tui.render import render_permission_prompt

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        display_args = display_arguments(tool_name, arguments, self.workdir)
        log = self.query_one("#transcript", RichLog)
        # Diff preview for write/edit (best-effort).
        diff = self._diff_preview(tool_name, display_args)
        prompt_text = render_permission_prompt(tool_name, display_args, diff)
        log.write(prompt_text)
        # v0.4.0.3: the PermissionAwareInput subclass intercepts y/a/n/p/Esc
        # while a permission is pending — no runtime bindings needed.
        self._pending_permission = {
            "future": future,
            "tool_name": tool_name,
            "arguments": arguments,
            "choices": {"y", "s", "a", "n", "p"},
        }
        # B.4: register the ask so /approve <id> / /deny <id> can resolve
        # it while the modal is open (or after the fact).
        self._approvals.register(tool_name, arguments, question, future)
        future.add_done_callback(
            lambda f: self._on_approval_resolved(tool_name, arguments, f)
        )
        # v0.4.0.2: ALWAYS restore the input when the future settles —
        # including the 600s timeout path in prompts.py, which would
        # otherwise leave the Input disabled forever ("hängt").
        future.add_done_callback(self._restore_input_after_permission)
        return future

    def _restore_input_after_permission(self, fut) -> None:
        """Clean up after a permission ask settles: re-enable + refocus.

        If the ask expired (600s timeout in prompts.py), the future is
        cancelled and the deny happens silently — say so in the
        transcript, otherwise the prompt looks still active and every
        key appears dead (v0.5.3 bug).
        """
        self._pending_permission = None
        if fut.cancelled():
            from contextlib import suppress

            with suppress(Exception):
                self.query_one("#transcript", RichLog).write(
                    "[yellow]⏱ permission request timed out — "
                    "automatically denied[/yellow]"
                )
        try:
            self.query_one("#input", Input).disabled = False
            self.query_one("#input", Input).focus()
        except Exception:
            pass

    def _diff_preview(self, tool_name: str, arguments: dict) -> str | None:
        """Best-effort unified-diff for write/edit calls (Phase B.2)."""
        if tool_name not in ("write", "edit"):
            return None
        try:
            from eaccode.ui.diff_renderer import build_unified_diff

            path_str = arguments.get("path", "")
            if not path_str:
                return None
            from pathlib import Path

            path = Path(path_str)
            if tool_name == "write":
                content = arguments.get("content", "")
                if path.exists():
                    old = path.read_text(encoding="utf-8", errors="replace")
                    return build_unified_diff(old, content, str(path))
                # new file — first 30 lines
                lines = content.splitlines()[:30]
                return ("--- /dev/null\n+++ " + str(path) + "\n"
                        + "\n".join(f"+{ln}" for ln in lines))
            # edit
            old = arguments.get("old_string", "")
            new = arguments.get("new_string", "")
            if not old or not path.exists():
                return None
            text = path.read_text(encoding="utf-8", errors="replace")
            return build_unified_diff(text, text.replace(old, new, 1),
                                      str(path))
        except Exception:
            return None

    def _resolve_pending_permission(self, choice: str) -> None:
        """Resolve the in-flight permission ask with *choice* (y/s/a/n/p)."""
        from eaccode.permissions.prompts import PermissionChoice

        pending = getattr(self, "_pending_permission", None)
        if not pending:
            return
        future = pending["future"]
        if future.done():
            return
        mapping = {
            "y": PermissionChoice.ALLOW_ONCE,
            "s": PermissionChoice.ALLOW_SESSION,
            "a": PermissionChoice.ALLOW_ALWAYS,
            "n": PermissionChoice.DENY,
            "p": PermissionChoice.PAUSE,
        }
        future.set_result(mapping[choice])
        # _pending_permission + input restore happen in the done_callback
        # (_restore_input_after_permission) — keep this method minimal.
        self.query_one("#transcript", RichLog).write(f"  → {choice}")

    def on_key(self, event) -> None:
        """v0.5.0: overlay navigation (↑↓ Tab Esc) + permission keys.

        The PermissionAwareInput handles y/a/n/p/Esc while a permission
        is pending; this app-level handler covers overlay navigation
        (arrow keys arrive here when the Input does not consume them).
        """
        key = event.key.lower()
        # Slash overlay navigation.
        if self._overlay.items:
            if key == "down":
                self._overlay.move(1)
                self._render_overlay()
                event.prevent_default()
                event.stop()
                return
            if key == "up":
                self._overlay.move(-1)
                self._render_overlay()
                event.prevent_default()
                event.stop()
                return
            if key == "tab":
                current = self._overlay.current()
                if current:
                    self._composer_insert(f"/{current['name']} ")
                event.prevent_default()
                event.stop()
                return
            if key == "escape":
                self._overlay.update("")
                self._render_overlay()
                event.prevent_default()
                event.stop()
                return
        # Permission fallback (primary path: PermissionAwareInput).
        if not getattr(self, "_pending_permission", None):
            return
        if key in ("y", "s", "a", "n", "p", "escape"):
            self._resolve_pending_permission("n" if key == "escape" else key)
            event.prevent_default()
            event.stop()

    def _render_overlay(self) -> None:
        try:
            overlay = self.query_one("#overlay", Static)
            overlay.update("\n".join(self._overlay.render_lines()))
        except Exception:
            pass

    def _on_approval_resolved(self, tool_name: str, arguments: dict, future) -> None:
        """P0.9 suggest-mode: after repeated approvals, offer /allow."""
        from eaccode.permissions.allowlist import suggest_pattern
        from eaccode.permissions.prompts import PermissionChoice

        try:
            choice = future.result()
        except (Exception, asyncio.CancelledError):
            return  # cancelled/timed-out asks are not approvals
        if choice not in (PermissionChoice.ALLOW_ONCE, PermissionChoice.ALLOW_ALWAYS):
            return
        pattern = suggest_pattern(tool_name, arguments)
        key = f"{tool_name}|{pattern}"
        count = self._approval_counts.get(key, 0) + 1
        self._approval_counts[key] = count
        if count >= 3:
            self._approval_counts[key] = 0  # one hint per pattern
            log = self.query_one("#transcript", RichLog)
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

        log = self.query_one("#transcript", RichLog)
        self._stream_text = ""
        self._reasoning_text = ""
        self._tool_starts: dict[str, float] = {}
        # v0.5.0: the spinner lives in the status rule (Hermes-style busy
        # indicator), not in a separate widget.
        self._spinner_line_idx = None
        # C.4: single-writer fence — a new turn supersedes this stream.
        # claim_stream_writer stores the token on self (P0.6 Bug 1 fix).
        from eaccode.llm.stream_fence import claim_stream_writer, fence_delta

        claim_stream_writer(self)
        writer_token = self._stream_writer_token
        # B.4: animated spinner while the agent works (v0.4.0: ASCII cycle,
        # line already written into the Log by _run_agent_streaming above).
        self._spinner_idx = 0
        self._spinner_interval = self.set_interval(0.125, self._tick_spinner)
        self._refresh_status_rule(busy=True, indicator="⠋", verb="working…")
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
            # v0.5.0: clear the busy indicator in the status rule.
            from contextlib import suppress

            with suppress(Exception):
                self._refresh_status_rule(busy=False, indicator="", verb="")
            self._spinner_line_idx = None

        def on_text(delta: str) -> None:
            if fence_delta(self, writer_token, delta) is None:
                return  # stale stream — a newer turn owns the UI
            _hide_spinner()
            self._stream_text += delta
            # v0.0.1: stream renders IN the transcript via the incremental
            # StreamingMarkdownRenderer (no full re-parse, no separate
            # static widget). The markdown fragment is written to the
            # RichLog directly and replaces the visible "live" line on
            # the next scroll.
            from eaccode.tui.streaming_md import StreamingMarkdownRenderer

            if not hasattr(self, "_stream_renderer"):
                self._stream_renderer = StreamingMarkdownRenderer()
            fragment = self._stream_renderer.feed(delta)
            if fragment:
                log.write(fragment)

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
            # v0.0.1: reasoning renders into the transcript directly.
            from rich.markup import escape as esc

            capped = self._reasoning_text[:2000]
            suffix = "…" if len(self._reasoning_text) > 2000 else ""
            log.write(f"[dim italic]🧠 {esc(capped)}{esc(suffix)}[/dim italic]")

        def on_tool_call(tc: ToolCall) -> None:
            _hide_spinner()
            self._stream_text = ""
            # v0.0.1: flush any pending streaming fragment, then reset the
            # renderer so the next stream starts clean.
            fragment = ""
            renderer = getattr(self, "_stream_renderer", None)
            if renderer is not None:
                fragment = renderer.finalize()
            if fragment:
                log.write(fragment)
            import time

            self._tool_starts[tc.id] = time.monotonic()
            if VerboseLevel.show_start(self.verbose_level):
                # Phase H.6: friendly verb label ("Running pytest…") instead
                # of the raw call expression when a verb is known.
                label = build_tool_label(tc.name, tc.arguments)
                if label:
                    # B3 (audit): escape everything that came from the
                    # model/tool before it hits the markup-enabled Log.
                    from rich.markup import escape as esc

                    log.write(f"[dim]{CHEVRON} {esc(label)}[/dim]")
                else:
                    card = build_call_card(
                        tc.name, tc.arguments,
                        full_args=VerboseLevel.show_full_args(self.verbose_level),
                    )
                    from rich.markup import escape as esc

                    log.write(f"[dim]{CHEVRON} {esc(card.call)}[/dim]")

        def on_tool_result(tc: ToolCall, result: ToolResult) -> None:
            import time

            from rich.markup import escape as esc

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
            preview_txt = f" {esc(card.result_preview)}" if card.result_preview else ""
            log.write(f"  [{style}]{mark}[/{style}] {esc(card.name)}{duration_txt}{preview_txt}")
            # Phase B.7: multi-line result preview with collapse.
            if card.result_lines and self.verbose_level in (
                VerboseLevel.ALL, VerboseLevel.VERBOSE,
            ):
                for line in card.result_lines:
                    log.write(f"    [dim]{esc(line)}[/dim]")
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
        # v0.0.1: stream fragments are already in the transcript via
        # the StreamingMarkdownRenderer. Only flush any leftover buffer
        # (e.g. an unclosed bold marker) — do NOT re-render the final
        # text, which would duplicate the output.
        self._last_answer = result.final_text
        renderer = getattr(self, "_stream_renderer", None)
        if renderer is not None:
            tail = renderer.finalize()
            if tail:
                log.write(tail)
            renderer.reset()
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
        # v0.5.0: Hermes-style status rule.
        self._refresh_status_rule(busy=False, verb="idle")
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

    def _current_branch(self) -> str:
        """Return the current git branch name (cached) or '' on failure.

        v0.0.1: the status rule shows the branch next to the model.
        The branch is probed via the existing bounded git probe utilities
        (or a 0.5s subprocess fallback) — never blocking the UI thread.
        """
        # Cache: avoid re-running git on every status refresh.
        cached = getattr(self, "_branch_cache", None)
        if cached is not None:
            return cached
        try:
            import subprocess as _sp

            from eaccode._subprocess_compat import (
                noninteractive_git_env,
                windows_popen_kwargs,
            )

            env = noninteractive_git_env()
            kwargs = {"capture_output": True, "text": True, "timeout": 0.5,
                      "env": env}
            kwargs.update(windows_popen_kwargs())
            proc = _sp.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                **kwargs,
            )
            branch = proc.stdout.strip() if proc.returncode == 0 else ""
        except Exception:
            branch = ""
        self._branch_cache = branch
        return branch

    def _spinner_frame(self) -> str:
        """Next ASCII spinner frame (Phase A.2: v0.4.0)."""
        from eaccode.tui.spinner import Spinner as _Spinner

        # Use a small standalone instance so the spinner's index advances
        # independently of the legacy _spinner_idx counter.
        spinner = _Spinner(interval=0.125)
        spinner.tick()
        return spinner.frame()

    def _tick_spinner(self) -> None:
        """v0.5.0: drive the busy indicator inside the status rule."""
        from eaccode.tui.spinner import Spinner as _Spinner

        if not self._busy:
            return
        self._spinner = getattr(self, "_spinner", _Spinner(interval=0.125))
        self._spinner.tick()
        self._refresh_status_rule(busy=True, indicator=self._spinner.frame())

    def _refresh_status_rule(self, *, busy: bool | None = None,
                             indicator: str | None = None,
                             verb: str | None = None) -> None:
        """v0.5.0: render the Hermes-style status rule (busy · model · ctx)."""
        from eaccode.tui.status_rule import StatusRule

        if busy is not None:
            self._status_busy = busy
        if indicator is not None:
            self._status_indicator = indicator
        if verb is not None:
            self._status_verb = verb
        ctx_used = None
        ctx_max = None
        if self.messages:
            try:
                # B8 (audit): real context numbers — the bar was dead
                # because context_max was hard-wired to None.
                from eaccode.llm.tokens import (
                    count_message_tokens,
                    model_context_window,
                )

                model = self._model_name or "default"
                ctx_max = model_context_window(model)
                ctx_used = count_message_tokens(self.messages, model)
            except Exception:
                pass
        rule = StatusRule(
            busy=getattr(self, "_status_busy", False),
            indicator=getattr(self, "_status_indicator", ""),
            verb=getattr(self, "_status_verb", ""),
            model=self._model_name or "—",
            branch=self._current_branch(),
            context_used=ctx_used,
            context_max=ctx_max,
            cost_usd=self._total_usage.cost_usd,
            right_label=self._session_title or str(self.workdir),
        )
        from contextlib import suppress

        with suppress(Exception):
            self.query_one("#status-rule", Static).update(rule.render())

    def action_open_palette(self) -> None:
        """Ctrl+K: open the filterable command palette (Phase F.3)."""
        from eaccode.ui.command_palette import CommandPalette

        def run(name: str) -> None:
            log = self.query_one("#transcript", RichLog)
            try:
                result = handle_command(name, self)
            except Exception as e:
                from eaccode.ui.commands import CommandResult

                result = CommandResult(message=f"✗ command error: {e}")
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
            self.query_one("#transcript", RichLog).write(
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
            self.query_one("#transcript", RichLog).write(
                f"✓ model switched to {name}"
            )
            # v0.5.0: refresh the status rule instead of sub_title.
            self._refresh_status_rule()
        except Exception as e:
            self.query_one("#transcript", RichLog).write(
                f"✗ model switch failed: {e}"
            )

    def _retry_last(self) -> str:
        """/retry: re-run the last user prompt (Phase B.3)."""
        import asyncio

        self._busy = True
        log = self.query_one("#transcript", RichLog)

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
            self.query_one("#transcript", RichLog).write(
                "[dim]Nothing to copy yet.[/dim]"
            )
            return
        from eaccode.ui.clipboard import write_clipboard_text

        try:
            if write_clipboard_text(self._last_answer):
                self.query_one("#transcript", RichLog).write(
                    "[dim]✓ Last answer copied to clipboard (paste with Ctrl+V)[/dim]"
                )
            else:
                self.query_one("#transcript", RichLog).write(
                    "[dim]✗ No clipboard tool available on this platform "
                    "(need wl-copy/xclip/xsel on Linux).[/dim]"
                )
        except Exception as e:
            self.query_one("#transcript", RichLog).write(
                f"[red]✗ Clipboard failed: {e}[/red]"
            )


def run_repl(workdir: Path | None = None, initial_messages: list | None = None) -> None:
    EaccodeApp(workdir=workdir, initial_messages=initial_messages).run()
