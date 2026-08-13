"""Plan 165-181 / Sprint 3.7: denial breach counter.

After a configurable number of denials within a window, the user's
intent is clearly "stop":

  0 denials       -> NONE   (ask normally)
  1               -> LOW    (ask normally)
  2-3             -> MEDIUM (ask but mention recent denials)
  4+              -> HIGH   (skip the question, refuse outright — the
                            user wants out)

Denials are namespaced by tool/heuristic so a denied bash command
doesn't poison the counter for unrelated write operations. The
counter auto-clears after ``window_seconds`` of inactivity.
"""

from __future__ import annotations

import time
from enum import Enum


class BreachLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BreachCounter:
    """Track recent denials so we can refuse outright after a few."""

    def __init__(
        self,
        window_seconds: float = 300.0,
        high_threshold: int = 4,
        medium_threshold: int = 2,
    ) -> None:
        self.window_seconds = window_seconds
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self._events: list[tuple[float, str]] = []

    def record_denial(self, reason: str = "") -> None:
        """Push one denial into the history."""
        self._events.append((time.monotonic(), reason))

    def clear(self) -> None:
        """Wipe the history (e.g. after explicit user /reset)."""
        self._events.clear()

    @property
    def deny_count(self) -> int:
        """Number of denials still inside the window (counts all reasons)."""
        cutoff = time.monotonic() - self.window_seconds
        self._events = [(t, r) for (t, r) in self._events if t >= cutoff]
        return len(self._events)

    @property
    def level(self) -> BreachLevel:
        n = self.deny_count
        if n == 0:
            return BreachLevel.NONE
        if n >= self.high_threshold:
            return BreachLevel.HIGH
        if n >= self.medium_threshold:
            return BreachLevel.MEDIUM
        return BreachLevel.LOW

    def note_for_user(self) -> str:
        """One-line message the REPL can prepend to the next prompt."""
        n = self.deny_count
        lvl = self.level
        if n == 0:
            return ""
        if lvl == BreachLevel.HIGH:
            return (
                f"[ ! ] {n} denials in the last "
                f"{int(self.window_seconds)}s — pausing prompts."
            )
        if lvl == BreachLevel.MEDIUM:
            return (
                f"[ i ] {n} denials so far. Continuing to ask for now, "
                f"but consider /yolo or --skip-rules."
            )
        return f"[ i ] {n} denial so far."
