"""Context compaction (Task 5.3) — summarize when the window gets full."""
from __future__ import annotations

from eaccode.llm.models import Message
from eaccode.llm.tokens import count_message_tokens, model_context_window


def should_compact(messages: list[Message], model: str, threshold: float) -> bool:
    window = model_context_window(model)
    used = count_message_tokens(messages, model)
    return used > window * threshold


def compact_messages(messages: list[Message], keep_recent: int = 5) -> list[Message]:
    """Drop old messages, keep recent ones. A system marker explains the gap."""
    if len(messages) <= keep_recent + 1:
        return messages
    summary = Message.system(
        "[Earlier conversation was compacted to save context. "
        "Tool calls and their results from earlier turns are no longer visible.]"
    )
    return [summary, *messages[-keep_recent:]]
