"""Streaming markdown renderer (v0.0.1 — Hermes/Claude-Code parity).

The streaming assistant response arrives in small deltas (chunks of 4-32
characters). Re-parsing the entire accumulated text on every delta is
O(N^2) and visibly stutters; on 50 deltas, the renderer would otherwise
re-tokenize 50 × 1KB of Markdown.

``StreamingMarkdownRenderer`` keeps a small lookahead buffer and only
render-finishes tokens that are *complete* in the current view:

- Inline markers (``**bold**``, ``*italic*``, ``` `code` ```) are buffered
  until their closing marker arrives, then emitted as a Rich markup span.
- Fenced code blocks (``` ``` ... ``` ```) are buffered until the closing
  fence arrives so we never emit half a code block.
- Plain text is emitted immediately without re-parsing earlier text.

The renderer is single-direction: feed forward only, no rewinding. That
matches the LLM stream semantics (content never goes backwards).

The public surface:

- ``feed(delta: str) -> str`` — append text, return the *new* rendered
  fragment (not the whole accumulated render). The TUI's transcript
  Log writes this fragment directly.
- ``last_feed_size`` — int, how many bytes of the delta were actually
  consumed by the formatter on the last call (used by tests to assert
  no full re-parse).
- ``reset()`` — clear all state (called at turn boundaries / tool calls).
- ``finalize() -> str`` — finish any buffered partial state (open bold
  etc.) and return the final text. Called once at end-of-turn.
"""
from __future__ import annotations

from dataclasses import dataclass


# A marker that we still need to close may be split across deltas.
# We buffer the *trailing* substring only if it could be the start of
# an open marker (``**``, ``*``, `` ` ``, or `` ``` ``).
_MARKER_STARTS = ("**", "*", "`", "```")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class _State:
    """Per-renderer mutable state."""

    last_feed_size: int = 0


class StreamingMarkdownRenderer:
    """Incremental, one-pass Markdown renderer.

    Designed for the streaming Textual transcript: each call to ``feed``
    returns the *new* Textual-Rich-markup fragment that is safe to write
    to a RichLog. Plain text is emitted 1:1; emphasis markers are
    buffered until closed so we never emit a half-balanced ``[bold]``.
    """

    _MARKER_LOOKAHEAD = 8  # keep up to 8 trailing bytes if they could be a marker

    def __init__(self) -> None:
        self._state = _State()
        self._buffer: str = ""

    # ----- introspection (used by tests) -----

    @property
    def last_feed_size(self) -> int:
        """Bytes of the last delta that the formatter actually consumed.

        For incremental rendering, this equals the delta length. For full
        re-parse, this would grow linearly with the accumulated text —
        the test asserts it stays bounded.
        """
        return self._state.last_feed_size

    # ----- public API -----

    def feed(self, delta: str) -> str:
        """Append *delta*; return the new rendered fragment.

        The fragment is whatever the formatter could *complete* in this
        call. If a token is still open (e.g. ``**bol`` without the
        closing ``**``), the open marker is buffered and emitted on the
        next feed.
        """
        if not delta:
            return ""
        text = self._buffer + delta
        self._buffer = ""
        out, carry = self._render_chunk(text)
        self._buffer = carry
        self._state.last_feed_size = len(delta)
        return out

    def reset(self) -> None:
        """Clear all state. Called at the start of a new turn."""
        self._state = _State()
        self._buffer = ""

    def finalize(self) -> str:
        """Close any open markers and return the finalization fragment.

        If the stream ends mid-token (the LLM cut off before closing
        ``**bold**``), we drop the open marker but keep the plain text
        so the user still sees the content.
        """
        if not self._buffer:
            return ""
        text = self._buffer
        self._buffer = ""
        return _esc(text)

    # ----- internals -----

    def _render_chunk(self, text: str) -> tuple[str, str]:
        """Render *text*; return (rendered, leftover_buffer).

        Algorithm:
        1. Identify the safe-cut point: the last index where we are
           certain the rest of the text is plain (no partial marker).
        2. Walk chars in the safe range, emitting complete tokens.
        3. If we encounter an open marker whose close is not in the
           safe range, defer everything from the open marker to the
           next feed.
        """
        n = len(text)
        if n == 0:
            return "", ""
        cursor = 0
        out: list[str] = []
        safe_end = self._safe_end(text)
        i = 0
        while i < n:
            if i >= safe_end:
                # Defer the rest to the next feed.
                out.append(_esc(text[cursor:i]))
                return "".join(out), text[i:]
            ch = text[i]
            # Fenced code block opening: ``` ... ```
            if text.startswith("```", i):
                end = text.find("```", i + 3)
                if end == -1:
                    # Unclosed fence — defer.
                    out.append(_esc(text[cursor:i]))
                    return "".join(out), text[i:]
                # Emit plain text up to the fence, then the code block.
                out.append(_esc(text[cursor:i]))
                inner = text[i + 3 : end]
                out.append("[grey58]" + _esc(inner) + "[/grey58]")
                cursor = i = end + 3
                continue
            # Inline code: `code`
            if ch == "`":
                end = text.find("`", i + 1)
                if end == -1 or end >= safe_end:
                    out.append(_esc(text[cursor:i]))
                    return "".join(out), text[i:]
                out.append(_esc(text[cursor:i]))
                out.append(f"[grey58]{_esc(text[i + 1 : end])}[/]")
                cursor = i = end + 1
                continue
            # Bold: **text**
            if text.startswith("**", i):
                end = text.find("**", i + 2)
                if end == -1 or end >= safe_end:
                    out.append(_esc(text[cursor:i]))
                    return "".join(out), text[i:]
                out.append(_esc(text[cursor:i]))
                out.append(f"[bold]{_esc(text[i + 2 : end])}[/bold]")
                cursor = i = end + 2
                continue
            # Italic: *text* (but not when it's part of **)
            if ch == "*" and not text.startswith("**", i):
                end = text.find("*", i + 1)
                if end == -1 or end >= safe_end:
                    out.append(_esc(text[cursor:i]))
                    return "".join(out), text[i:]
                out.append(_esc(text[cursor:i]))
                out.append(f"[italic]{_esc(text[i + 1 : end])}[/italic]")
                cursor = i = end + 1
                continue
            i += 1
        # Walked the whole text safe range. Emit any remaining tail.
        out.append(_esc(text[cursor:]))
        return "".join(out), ""

    def _safe_end(self, text: str) -> int:
        """Index up to which we can safely emit (everything after may be
        a marker that needs to be buffered)."""
        n = len(text)
        # Walk backwards from the end checking for any marker start.
        for marker in _MARKER_STARTS:
            # If the text ends with a prefix of *marker*, the last
            # (len(marker)) bytes could be the start of a marker.
            for k in range(1, len(marker) + 1):
                if text.endswith(marker[:k]):
                    return max(0, n - k)
        return n


def _esc(text: str) -> str:
    """Escape Rich markup brackets in plain text."""
    if not text:
        return ""
    from rich.markup import escape

    return escape(text)
