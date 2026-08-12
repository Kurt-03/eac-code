"""Classic REPL — pure-stdout chat loop (v0.7.2+).

Replaces the Textual TUI. The terminal owns the screen, so mouse text
selection works the same as in any normal cmd/PowerShell window.

Input: prompt_toolkit with FileHistory (cross-platform: Win/macOS/Linux).
Output: plain stdout, no markup. Stream tokens inline so the user sees
the agent "typing" (Claude Code-style).

Multi-line input: type ``\"\"\"`` on its own line to enter multi-line
mode; finish with another ``\"\"\"`` line.
"""

from __future__ import annotations

import asyncio
import queue
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from eaccode.agent.factory import build_agent_async
from eaccode.agent.runner import AgentEvent, run_repl_sync
from eaccode.config.paths import EaccodePaths
from eaccode.permissions.prompts import PermissionChoice
from eaccode.ui.context import ReplContext
from eaccode.ui.dispatch import dispatch_slash
from eaccode.ui.messages import banner, render_event_plain

PROMPT = "eaccode> "
MULTILINE_SENTINEL = '"""'


def run_repl(workdir: Path | None = None,
             initial_messages: list | None = None) -> None:
    """Run the classic REPL."""
    paths = EaccodePaths()
    history_path = paths.config_dir / "repl_history.txt"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    session: PromptSession[str] = PromptSession(history=FileHistory(str(history_path)))

    print(banner())
    print()

    ctx = ReplContext(workdir=workdir)
    messages: list = initial_messages or []
    ctx.state["messages"] = messages

    # Async init of the agent (LLMClient is async-only).
    try:
        agent, _, _ = asyncio.run(build_agent_async(workdir=workdir))
    except Exception as e:
        print(f"[ X ] Agent init failed: {e}")
        print("    Run `eaccode providers add` to configure a provider.")
        print("    (no LLM needed for /help, /status, /mode listing)")
        agent = None
    ctx.agent = agent
    if agent is not None and hasattr(agent, "policy"):
        ctx.policy = agent.policy

    while True:
        try:
            text, multiline = _read_input(session)
        except KeyboardInterrupt:
            print("\n[ i ] interrupted.")
            continue
        except EOFError:
            print()
            return

        if text is None:
            return  # /exit
        if not text.strip():
            continue

        if text.startswith("/"):
            output, should_exit = dispatch_slash(text, ctx)
            if output:
                print(output)
            if should_exit:
                return
            continue

        messages.append({"role": "user", "content": text})
        ctx.state["messages"] = messages

        if agent is None:
            print("[ X ] No agent available. Run `eaccode providers add`.")
            continue

        # Shared queue between REPL main thread and agent worker thread:
        # REPL puts (ask_id, choice) tuples in, worker resolves the
        # matching asyncio.Future.
        resolves: queue.Queue = queue.Queue()

        # Run the turn. The runner drives the agent on a worker thread
        # and yields events back; we print inline.
        try:
            for event in run_repl_sync(agent, messages, resolve_queue=resolves):
                _handle_event(event, ctx, messages, resolves)
        except KeyboardInterrupt:
            print("\n[ i ] turn cancelled.")
        except Exception as e:
            print(f"\n[ X ] agent loop error: {e}")
        # After the turn, sync messages from the agent (it appends tool
        # rows internally).
        try:
            updated = agent.messages
            if isinstance(updated, list):
                messages.clear()
                messages.extend(updated)
                ctx.state["messages"] = messages
        except Exception:
            pass
        print()


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
) -> None:
    """Print one AgentEvent. Inline tokens stay inline."""
    if event.kind == "text":
        delta = event.payload.get("delta", "")
        if delta:
            sys.stdout.write(delta)
            sys.stdout.flush()
        return
    if event.kind == "reasoning":
        # Reasoning: never inline — wrap in dim-ish line once it arrives.
        delta = event.payload.get("delta", "")
        if delta:
            sys.stdout.write(delta)
            sys.stdout.flush()
        return
    if event.kind == "permission":
        # Print the question, read the answer from stdin.
        sys.stdout.write("\n")
        sys.stdout.flush()
        sys.stdout.write(render_event_plain(event))
        sys.stdout.flush()
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            line = "n"
        choice = _parse_choice(line)
        ask_id = event.payload.get("id")
        resolves.put((ask_id, choice))
        return
    if event.kind == "tool_call":
        # End any in-progress inline text on a new line, then the card.
        sys.stdout.write("\n")
        sys.stdout.write(render_event_plain(event) + "\n")
        sys.stdout.flush()
        return
    if event.kind == "tool_result":
        sys.stdout.write(render_event_plain(event) + "\n")
        sys.stdout.flush()
        return
    if event.kind == "usage":
        sys.stdout.write(render_event_plain(event) + "\n")
        sys.stdout.flush()
        return
    if event.kind == "error":
        sys.stdout.write("\n" + render_event_plain(event) + "\n")
        sys.stdout.flush()
        return
    if event.kind == "done":
        sys.stdout.write("\n")
        sys.stdout.flush()
        return


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
