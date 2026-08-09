"""Stateful scrubber for reasoning/thinking blocks in streamed text.

Ported from Hermes' ``agent/think_scrubber.py`` (MIT, Aug 2026).

Why stateful: MiniMax streams thinking blocks SPLIT across deltas
(``<thi`` + ``nk>...`` + ``</think>``). A per-delta regex erases the
first delta entirely and never sees the open tag, so downstream consumers
treat the thinking as regular content and leak it to the user.

State machine:
- ``_in_block``: True while inside an opened block; all text is discarded.
- ``_buf``: held-back partial-tag tail, resolved on the next feed().
- ``_last_emitted_ended_newline``: boundary gating so prose that merely
  mentions '<think>' isn't over-stripped.

Recognized tags: think, thinking, reasoning, thought, REASONING_SCRATCHPAD.
"""

from __future__ import annotations


class StreamingThinkScrubber:
    """Stateful scrubber for streaming reasoning/thinking blocks."""

    _OPEN_TAG_NAMES: tuple[str, ...] = (
        "think", "thinking", "reasoning", "thought", "REASONING_SCRATCHPAD",
    )
    _OPEN_TAGS: tuple[str, ...] = tuple(f"<{n}>" for n in _OPEN_TAG_NAMES)
    _CLOSE_TAGS: tuple[str, ...] = tuple(f"</{n}>" for n in _OPEN_TAG_NAMES)
    _MAX_TAG_LEN: int = max(len(t) for t in _OPEN_TAGS + _CLOSE_TAGS)

    def __init__(self) -> None:
        self._in_block = False
        self._buf = ""
        self._last_emitted_ended_newline = True

    def reset(self) -> None:
        """Reset all state — call at the top of every new turn."""
        self._in_block = False
        self._buf = ""
        self._last_emitted_ended_newline = True

    # ------------------------------------------------------------ internals

    def _find_first_tag(self, buf: str, tags: tuple[str, ...]) -> tuple[int, int] | None:
        best: tuple[int, int] | None = None
        for tag in tags:
            idx = buf.find(tag)
            if idx != -1 and (best is None or idx < best[0]):
                best = (idx, len(tag))
        return best

    def _max_partial_suffix(self, buf: str, tags: tuple[str, ...]) -> int:
        """Length of the longest suffix that could be a split tag prefix."""
        best = 0
        for tag in tags:
            for cut in range(1, min(len(tag), len(buf)) + 1):
                if buf.endswith(tag[:cut]):
                    best = max(best, cut)
        return best

    def _find_earliest_closed_pair(self, buf: str) -> tuple[int, int] | None:
        """Find the earliest complete <tag>X</tag> pair anywhere in buf."""
        best: tuple[int, int] | None = None
        for open_tag, close_tag in zip(self._OPEN_TAGS, self._CLOSE_TAGS, strict=True):
            start = buf.find(open_tag)
            if start == -1:
                continue
            end = buf.find(close_tag, start + len(open_tag))
            if end == -1:
                continue
            candidate = (start, end + len(close_tag))
            if best is None or candidate[0] < best[0]:
                best = candidate
        return best

    def _find_open_at_boundary(self, buf: str, out: list[str]) -> tuple[int, int] | None:
        """Unterminated open tag at a block boundary (start of buf, or right
        after a newline in the already-emitted portion)."""
        for tag in self._OPEN_TAGS:
            idx = buf.find(tag)
            if idx == -1:
                continue
            if idx == 0 and self._last_emitted_ended_newline:
                return (idx, len(tag))
            # After a newline inside the current buffer.
            nl = buf.rfind("\n", 0, idx)
            if nl != -1 and idx == nl + 1:
                return (idx, len(tag))
        return None

    @staticmethod
    def _strip_orphan_close_tags(text: str) -> str:
        for tag in StreamingThinkScrubber._CLOSE_TAGS:
            text = text.replace(tag, "")
        return text

    # ---------------------------------------------------------------- feed

    def feed(self, text: str) -> str:
        """Feed one delta; return the scrubbed visible portion.

        May return an empty string when the entire delta is reasoning
        content or is held back pending resolution of a partial tag.
        """
        if not text:
            return ""
        buf = self._buf + text
        self._buf = ""
        out: list[str] = []

        while buf:
            if self._in_block:
                close = self._find_first_tag(buf, self._CLOSE_TAGS)
                if close is None:
                    held = self._max_partial_suffix(buf, self._CLOSE_TAGS)
                    self._buf = buf[-held:] if held else ""
                    return "".join(out)
                buf = buf[close[0] + close[1]:]
                self._in_block = False
            else:
                pair = self._find_earliest_closed_pair(buf)
                open_at = self._find_open_at_boundary(buf, out)

                if pair is not None and (open_at is None or pair[0] <= open_at[0]):
                    start, end = pair
                    preceding = buf[:start]
                    if preceding:
                        preceding = self._strip_orphan_close_tags(preceding)
                        if preceding:
                            out.append(preceding)
                            self._last_emitted_ended_newline = preceding.endswith("\n")
                    buf = buf[end:]
                    continue

                if open_at is not None:
                    idx, tag_len = open_at
                    preceding = buf[:idx]
                    if preceding:
                        preceding = self._strip_orphan_close_tags(preceding)
                        if preceding:
                            out.append(preceding)
                            self._last_emitted_ended_newline = preceding.endswith("\n")
                    self._in_block = True
                    buf = buf[idx + tag_len:]
                    continue

                held = max(
                    self._max_partial_suffix(buf, self._OPEN_TAGS),
                    self._max_partial_suffix(buf, self._CLOSE_TAGS),
                )
                if held:
                    emit_text = buf[:-held]
                    self._buf = buf[-held:]
                else:
                    emit_text = buf
                    self._buf = ""
                if emit_text:
                    emit_text = self._strip_orphan_close_tags(emit_text)
                    if emit_text:
                        out.append(emit_text)
                        self._last_emitted_ended_newline = emit_text.endswith("\n")
                return "".join(out)

        return "".join(out)
