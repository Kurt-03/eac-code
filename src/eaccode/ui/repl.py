"""Classic REPL — pure-stdout chat loop (v0.7.2+, Rich-rendered in v0.7.3).

Replaces the Textual TUI. The terminal owns the screen, so mouse text
selection works the same as in any normal cmd/PowerShell window.

Input: prompt_toolkit with FileHistory (cross-platform: Win/macOS/Linux).
Output: one Rich Console with a Hermes-style theme — tool cards,
banner, permission prompt, status, errors. When stdout is not a TTY,
Rich disables its Live overlay and prints plain lines (no ANSI noise
when ``eaccode run --print`` is redirected to a file).

Multi-line input: type ``\"\"\"`` on its own line to enter multi-line
mode; finish with another ``\"\"\"`` line.
"""

from __future__ import annotations

import asyncio
import queue
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from eaccode import __version__
from eaccode.agent.factory import build_agent_async
from eaccode.agent.runner import AgentEvent, run_repl_sync
from eaccode.config.paths import EaccodePaths
from eaccode.permissions.prompts import PermissionChoice
from eaccode.ui.context import ReplContext
from eaccode.ui.dispatch import dispatch_slash
from eaccode.ui.rich_console import (
    make_console,
    render_assistant_delta,
    render_assistant_finish,
    render_banner,
    render_error,
    render_info,
    render_permission_prompt,
    render_tool_call,
    render_tool_result,
    render_user_prompt,
)

PROMPT = "eaccode> "
MULTILINE_SENTINEL = '"""'


def run_repl(workdir: Path | None = None,
             initial_messages: list | None = None) -> None:
    """Run the classic REPL."""
    # Console: trust Rich's terminal detection. When stdout is redirected
    # to a file Rich disables Live automatically.
    con = make_console()

    paths = EaccodePaths()
    history_path = paths.config_dir / "repl_history.txt"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    session: PromptSession[str] = PromptSession(history=FileHistory(str(history_path)))

    workdir = workdir or Path.cwd()

    ctx = ReplContext(workdir=workdir)
    messages: list = initial_messages or []
    ctx.state["messages"] = messages

    # Async init of the agent (LLMClient is async-only).
    try:
        agent, _, _ = asyncio.run(build_agent_async(workdir=workdir))
    except Exception as e:
        render_error(con, f"Agent init failed: {e}")
        import traceback
        con.print(traceback.format_exc())
        render_info(con, "Run `eaccode providers add` to configure a provider.")
        render_info(con, "(no LLM needed for /help, /status, /mode listing)")
        agent = None
    ctx.agent = agent
    if agent is not None and hasattr(agent, "policy"):
        ctx.policy = agent.policy

    # Banner: name, version, mode, model, workdir (Plan 274).
    model_name = getattr(agent, "client", None)
    model_name = getattr(model_name, "default_model", "—") if model_name else "—"
    mode_name = (ctx.policy.mode.value if ctx.policy else "manual")
    render_banner(con, version=__version__, workdir=workdir,
                  model=model_name, mode=mode_name)

    while True:
        try:
            text, multiline = _read_input(session)
        except KeyboardInterrupt:
            render_info(con, "interrupted.")
            continue
        except EOFError:
            con.print()
            return

        if text is None:
            return  # /exit
        if not text.strip():
            continue

        if text.startswith("/"):
            output, should_exit = dispatch_slash(text, ctx)
            if output:
                con.print(output)
            if should_exit:
                return
            continue

        # Echo the user prompt with the › glyph.
        render_user_prompt(con, text)

        messages.append({"role": "user", "content": text})
        ctx.state["messages"] = messages

        if agent is None:
            render_error(con, "No agent available. Run `eaccode providers add`.")
            continue

        # Shared queue between REPL main thread and agent worker thread:
        # REPL puts (ask_id, choice) tuples in, worker resolves the
        # matching asyncio.Future.
        resolves: queue.Queue = queue.Queue()

        # Run the turn. The runner drives the agent on a worker thread
        # and yields events back; we print inline.
        try:
            for event in run_repl_sync(agent, messages, resolve_queue=resolves):
                _handle_event(event, ctx, messages, resolves, con)
        except KeyboardInterrupt:
            render_info(con, "turn cancelled.")
        except Exception as e:
            render_error(con, f"agent loop error: {e}")
        con.print()


def _read_input(session: PromptSession[str]) -> tuple[str | None, bool]:
    """Read one user prompt. Supports multi-line via ``\"\"\"`` sentinel."""
    first = session.prompt(PROMPT)
    if first is None:
        return None, False
    if first.strip() == MULTILINE_SENTINEL:
        return _read_multiline(session), True
    return first, False


def _read_multiline(session: PromptSession[str]) -> str:
    """Collect lines until a ``\"\"\"`` is the only content of a line."""
    print("[ i ] multi-line mode — finish with a line containing only \"\"\"")
    lines: list[str] = []
    while True:
        try:
            line = session.prompt("... ")
        except (EOFError, KeyboardInterrupt):
            print()
            return "\n".join(lines)
        if line.strip() == MULTILINE_SENTINEL:
            return "\n".join(lines)
        lines.append(line)


def _handle_event(
    event: AgentEvent,
    ctx: ReplContext,
    messages: list,
    resolves: queue.Queue,
    con,
) -> None:
    """Render one AgentEvent through the shared Rich console."""
    if event.kind == "text":
        delta = event.payload.get("delta", "")
        if delta:
            render_assistant_delta(con, delta)
        return
    if event.kind == "reasoning":
        # P0.4 (audit): reasoning must not leak into the user-visible
        # transcript. Show only when explicitly toggled on, in its own
        # dim line, then close the block on the first text delta.
        if not getattr(ctx, "show_reasoning", False):
            return
        delta = event.payload.get("delta", "")
        if delta:
            con.out(delta, end="", style="reasoning")
        return
    if event.kind == "permission":
        render_assistant_finish(con)
        tool = event.payload.get("tool", "?")
        question = event.payload.get("question", f"Allow {tool}?")
        approval_id = event.payload.get("id")
        render_permission_prompt(con, tool=tool, question=question,
                                  approval_id=approval_id)
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            line = "n"
        choice = _parse_choice(line)
        resolves.put((approval_id, choice))
        return
    if event.kind == "tool_call":
        render_assistant_finish(con)
        render_tool_call(
            con,
            tool_name=event.payload.get("name", "?"),
            arguments=event.payload.get("arguments", {}) or {},
        )
        return
    if event.kind == "tool_result":
        content = (event.payload.get("content") or "").strip()
        # First line for the inline preview; the rest stays in the
        # transcript scrollback via tool_call/result pairing.
        first_line = content.splitlines()[0] if content else ""
        render_tool_result(
            con,
            tool_name=event.payload.get("name", "?"),
            content=first_line,
            is_error=bool(event.payload.get("is_error", False)),
            duration_s=None,            # runner doesn't send timing yet
            arguments=event.payload.get("arguments", {}) or {},
        )
        return
    if event.kind == "usage":
        ti = event.payload.get("tokens_in", 0)
        to = event.payload.get("tokens_out", 0)
        cost = event.payload.get("cost_usd", 0.0)
        render_info(con, f"tokens in={ti} out={to} cost=${cost:.4f}")
        return
    if event.kind == "error":
        render_assistant_finish(con)
        render_error(con, event.payload.get("message", "unknown error"))
        return
    if event.kind == "done":
        render_assistant_finish(con)
        return
    if event.kind == "result":
        # P0.3 (audit): the agent built up an authoritative message
        # list (assistant turns, tool calls, tool results). Adopt it
        # verbatim so the next turn sees the full context — without
        # this, the agent forgets its own previous answers.
        new_msgs = event.payload.get("messages") or []
        if new_msgs:
            messages.clear()
            messages.extend(_messages_to_dicts(new_msgs))
            ctx.state["messages"] = messages
        return


def _messages_to_dicts(messages) -> list[dict]:
    """P0.3: convert agent Message objects to plain dicts for persistence."""
    out: list[dict] = []
    for m in messages:
        role = getattr(m.role, "value", m.role)
        text_parts = []
        for block in (m.content or []):
            t = getattr(block, "type", None)
            if t == "text":
                text_parts.append(block.text)
        content_str = "".join(text_parts)
        entry: dict = {"role": role, "content": content_str}
        if getattr(m, "tool_calls", None):
            entry["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in m.tool_calls
            ]
        if getattr(m, "tool_call_id", None):
            entry["tool_call_id"] = m.tool_call_id
        if getattr(m, "name", None):
            entry["name"] = m.name
        out.append(entry)
    return out


def _parse_choice(line: str) -> PermissionChoice:
    """Map a raw stdin line to a PermissionChoice."""
    s = line.strip().lower()
    if s in ("y", "yes"):
        return PermissionChoice.ALLOW_ONCE
    if s == "a":
        return PermissionChoice.ALLOW_ALWAYS
    if s == "s":
        return PermissionChoice.ALLOW_SESSION
    if s == "p":
        return PermissionChoice.PAUSE
    # Default = deny on anything else (incl. empty / Esc)
    return PermissionChoice.DENY
