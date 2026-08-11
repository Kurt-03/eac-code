"""Background-review scheduler (C.1) — when to run a post-turn review.

Pure turn counting: the REPL asks ``should_review(turns)`` after each
agent run and launches the review worker (background_review.py) when the
window is reached. ``review_every_turns == 0`` disables reviews.
"""

from __future__ import annotations


class ReviewScheduler:
    def __init__(self, every_turns: int = 5) -> None:
        self.every_turns = max(0, every_turns)
        self._turns_since_review = 0

    @property
    def enabled(self) -> bool:
        return self.every_turns > 0

    def should_review(self, turns: int) -> bool:
        """True when *turns* completes a window since the last review."""
        if not self.enabled:
            return False
        self._turns_since_review += max(0, turns)
        if self._turns_since_review >= self.every_turns:
            self._turns_since_review = 0
            return True
        return False

    def reset(self) -> None:
        self._turns_since_review = 0
