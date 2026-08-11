"""Runtime helpers (F.8) — small, shared agent-loop utilities.

Kept separate from loop.py so they stay unit-testable without a client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def is_final_response(text: str) -> bool:
    """A response is final when it has real content (not empty/whitespace)."""
    return bool(text and text.strip())


def extract_text(content: Any) -> str:
    """Message text from a content blob (str, list of blocks, or None)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    parts.append(block["text"])
                elif block.get("type") == "tool_use" and block.get("name"):
                    parts.append(f"[tool: {block['name']}]")
        return " ".join(parts)
    return str(content)


def summarize_reasoning(text: str, max_chars: int = 160) -> str:
    """F.20: single-line reasoning summary for collapsed display."""
    one_line = " ".join(text.split())
    if len(one_line) <= max_chars:
        return one_line
    return one_line[:max_chars].rstrip() + "…"


def merge_usage(a: Any, b: Any) -> Any:
    """Add b's token/cost counters onto a (in place); returns a."""
    if a is None:
        return b
    if b is None:
        return a
    try:
        a.input_tokens += b.input_tokens
        a.output_tokens += b.output_tokens
        a.cost_usd += b.cost_usd
    except AttributeError:
        pass
    return a


@dataclass
class TurnContext:
    """F.9 — per-turn bookkeeping handed to hooks/finalizers."""

    turn: int
    messages_before: int
    tokens_before: int
    retries: int = 0


@dataclass
class TurnRetryState:
    """F.10 — transient-failure retry bookkeeping for one turn."""

    max_retries: int = 2
    attempts: int = 0
    last_error: str = ""

    @property
    def exhausted(self) -> bool:
        return self.attempts >= self.max_retries

    def record_failure(self, error: str) -> None:
        self.attempts += 1
        self.last_error = error


@dataclass
class IterationBudget:
    """F.12 — hard limits for a run: turns, tokens, wall-clock deadline."""

    max_turns: int = 30
    max_tokens: int = 0  # 0 = unlimited
    deadline: float | None = None  # unix timestamp

    def exhausted(self, turn: int, tokens_used: int) -> bool:
        if turn >= self.max_turns:
            return True
        if self.max_tokens and tokens_used >= self.max_tokens:
            return True
        if self.deadline is not None:
            import time

            if time.time() >= self.deadline:
                return True
        return False

    def remaining(self, turn: int, tokens_used: int) -> int:
        """Approximate remaining turns (for status output)."""
        if self.exhausted(turn, tokens_used):
            return 0
        return self.max_turns - turn
