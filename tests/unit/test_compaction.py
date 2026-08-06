"""Tests for context compaction (Task 5.3)."""
from eaccode.agent.compaction import compact_messages, should_compact
from eaccode.llm.models import Message


def test_should_compact_below_threshold():
    msgs = [Message.user("short")]
    assert should_compact(msgs, model="anthropic/claude-sonnet-4-6", threshold=0.7) is False


def test_should_compact_above_threshold():
    # 50K distinct words ≈ ~150K tokens (repetitive strings tokenize too
    # efficiently to test this) — comfortably above 70% of the 200K window
    text = " ".join(f"word{i}" for i in range(50_000))
    msgs = [Message.user(text)]
    assert should_compact(msgs, model="anthropic/claude-sonnet-4-6", threshold=0.7) is True


def test_compact_preserves_recent():
    msgs = [Message.user(f"msg {i}") for i in range(20)]
    compacted = compact_messages(msgs, keep_recent=3)
    assert len(compacted) <= 4  # summary + 3 recent


def test_compact_small_history_unchanged():
    msgs = [Message.user("a"), Message.user("b")]
    assert compact_messages(msgs, keep_recent=5) == msgs


def test_compact_marks_summary():
    msgs = [Message.user(f"msg {i}") for i in range(10)]
    compacted = compact_messages(msgs, keep_recent=2)
    assert compacted[0].role.value == "system"
    assert "compacted" in compacted[0].text.lower()
