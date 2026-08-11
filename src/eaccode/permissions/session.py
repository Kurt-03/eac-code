"""Session pause flag (P0.8) — the `P` approve level.

When the user picks Pause in the permission modal, every further tool
call is rejected with a clear hint until the session is resumed
(``/resume`` in the REPL). Headless contexts simply never create a flag.
"""

from __future__ import annotations


class PauseFlag:
    """Thread-trivial session state; the REPL owns one instance."""

    def __init__(self) -> None:
        self.paused = False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False
