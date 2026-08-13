"""Rich-based REPL rendering (Plan P2).

The classic REPL owns one Console instance with a tiny theme so tool
cards, the spinner overlay, and the version banner all look consistent.
When stdout is not a TTY (e.g. ``eaccode run --print`` redirected to a
file) Rich disables its Live overlay automatically; we keep printing
plain lines so logs stay ANSI-free.
"""

from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text
from rich.theme import Theme

from eaccode.ui.messages import _one_arg_summary

# Hermes-style theme: muted palette, single accent for the prompt glyph.
_THEME = Theme({
    "prompt":       "bold cyan",
    "user":         "bold white",
    "assistant":    "white",
    "reasoning":    "dim italic",
    "tool.call":    "bold yellow",
    "tool.ok":      "green",
    "tool.err":     "bold red",
    "tool.preview": "dim",
    "info":         "dim cyan",
    "warn":         "yellow",
    "error":        "bold red",
    "status":       "dim",
    "border":       "dim cyan",
})


def make_console(*, file: io.IOBase | None = None, force_terminal: bool | None = None) -> Console:
    """One Console per REPL run.

    ``force_terminal`` overrides Rich's auto-detection — useful for
    the test suite (we want plain text, no live overlay) and for the
    ``--print`` headless path (plain ANSI-free lines into a file).
    """
    if force_terminal is None:
        # Default: trust Rich's is_terminal, which checks the file object.
        terminal = None
    else:
        terminal = force_terminal
    return Console(
        theme=_THEME,
        file=file,
        force_terminal=terminal,
        highlight=False,   # we control our own markup
        markup=False,
        record=False,
    )


def render_banner(console: Console, *, version: str, workdir: Path,
                  model: str, mode: str) -> None:
    """Print the first-line greeting per Plan 274.

    Three lines, dim-friendly: name, version, mode/model/workdir.
    """
    from rich.rule import Rule

    console.print(Rule("[bold cyan]eaccode[/bold cyan]", style="border"))
    console.print(
        f"  [prompt]eaccode[/prompt] [dim]v{version}[/dim]  "
        f"[info]{mode}[/info]  [status]{model}[/status]"
    )
    console.print(f"  [dim]workdir:[/dim] {workdir}")
    console.print(Rule(style="border"))


def render_tool_call(console: Console, *, tool_name: str, arguments: dict) -> None:
    """Tool-card headline (Plan 255-263).

    One meaningful argument instead of dumping every key=value. Paths
    and commands stay copy-pasteable.
    """
    headline = _one_arg_summary(tool_name, arguments)
    if headline:
        console.print(f"  [tool.call]▸[/tool.call] [bold]{tool_name}[/bold] {headline}")
    else:
        console.print(f"  [tool.call]▸[/tool.call] [bold]{tool_name}[/bold]")


def render_tool_result(console: Console, *, tool_name: str,
                       content: str, is_error: bool,
                       duration_s: float | None,
                       arguments: dict | None = None,
                       result_max: int = 120) -> None:
    """Tool-card result (Plan 256).

    One-line summary: mark + name + duration + first-line preview.
    Multi-line output is shown only when verbose is on; the caller
    passes already-truncated content.
    """
    mark = "✗" if is_error else "✓"
    style = "tool.err" if is_error else "tool.ok"
    dur = f" [dim]· {duration_s:.1f}s[/dim]" if duration_s is not None else ""
    preview = ""
    first_line = (content or "").splitlines()[0] if content else ""
    if first_line:
        snippet = first_line[:result_max]
        if len(first_line) > result_max:
            snippet += "…"
        preview = f"  [tool.preview]{snippet}[/tool.preview]"
    console.print(f"  [{style}]{mark}[/{style}] [bold]{tool_name}[/bold]{dur}{preview}")


def render_error(console: Console, message: str) -> None:
    console.print(f"  [error][ X ] {message}[/error]")


def render_info(console: Console, message: str) -> None:
    console.print(f"  [info][ i ] {message}[/info]")


def render_warn(console: Console, message: str) -> None:
    console.print(f"  [warn][ ! ] {message}[/warn]")


def render_user_prompt(console: Console, text: str) -> None:
    """Echo the user prompt with the › glyph (Plan 273)."""
    console.print(f"  [prompt]❯[/prompt] [user]{text}[/user]")


def render_assistant_delta(console: Console, delta: str) -> None:
    """Inline token printing via ``console.out(end='')``.

    Plan 274: streaming text uses ``console.out(delta, end='')``, not
    ``console.print``.
    """
    console.out(delta, end="")


def render_assistant_finish(console: Console) -> None:
    """Trailing newline when the assistant's stream ends (Plan 274)."""
    console.out("\n")


def render_permission_prompt(console: Console, *, tool: str,
                              question: str, approval_id: int | None) -> None:
    """The numbered permission question (Plan 184-203).

    The actual key handling (y/a/n/p/Esc) is still driven by ``input()``
    — Rich only formats the question.
    """
    id_tag = f" [dim]#{approval_id}[/dim]" if approval_id is not None else ""
    console.print()
    console.print(Panel(
        f"  [warn]{question}[/warn]",
        border_style="warn",
        title=f"[bold]⚠ permission required · {tool}[/bold]{id_tag}",
        title_align="left",
        padding=(0, 2),
    ))
    console.print("  [dim]y[/dim]=once  [dim]a[/dim]=always  "
                  "[dim]n[/dim]=deny  [dim]p[/dim]=pause  "
                  "[dim]Esc[/dim]=deny", end="")
    console.out(" ")


def render_status(console: Console, *, model: str, mode: str, workdir: Path,
                  session_rules: list[str], allowlist_size: int,
                  total_usage_tokens: tuple[int, int] = (0, 0)) -> None:
    """/status display (Plan 279)."""
    console.print("[bold]/status[/bold]")
    console.print(f"  [dim]model[/dim]   {model}")
    console.print(f"  [dim]mode[/dim]    {mode}")
    console.print(f"  [dim]workdir[/dim] {workdir}")
    console.print(
        f"  [dim]session[/dim]  {len(session_rules)} active rule(s)"
    )
    console.print(
        f"  [dim]allowlist[/dim] {allowlist_size} persistent entries"
    )
    in_t, out_t = total_usage_tokens
    console.print(
        f"  [dim]tokens[/dim]   in={in_t} out={out_t}"
    )


class SpinnerOverlay:
    """A single bottom-line spinner that pauses for stdin input (Plan 257-259).

    Rich's ``Live`` renders a ``Spinner`` to its own console stream and
    automatically stops for the user prompt (when the REPL calls
    ``pause()`` before ``input()``). When the agent finishes, call
    ``stop()`` to clear the line before the next transcript entry.
    """

    def __init__(self, console: Console, label: str = "working"):
        # Use a Spinner with a short label so the line stays compact.
        self._console = console
        self._live: Live | None = Live(
            Spinner("dots", text=Text(f" {label}…", style="status")),
            console=console,
            transient=True,
            refresh_per_second=12,
        )

    def __enter__(self) -> SpinnerOverlay:
        if self._console.is_terminal:
            self._live.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._live is not None:
            self._live.__exit__(exc_type, exc, tb)
            self._live = None

    def update(self, label: str) -> None:
        if self._live is not None:
            self._live.update(
                Spinner("dots", text=Text(f" {label}…", style="status"))
            )

    def stop(self) -> None:
        """Stop the live overlay explicitly (e.g. before printing a result)."""
        if self._live is not None:
            self._live.stop()
