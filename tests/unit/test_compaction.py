"""Tests for smart context compaction (P0.2) — soft tail, ghost defense,
feasibility skip, small-window floor, session-boundary redaction."""

from eaccode.agent.compaction import (
    GHOST_MARKER,
    compact_messages,
    effective_threshold,
    should_compact,
)
from eaccode.llm.models import Message, TextContent, ToolCall


def test_should_compact_below_threshold():
    msgs = [Message.user("short")]
    assert should_compact(msgs, model="anthropic/claude-sonnet-4-6", threshold=0.7) is False


def test_should_compact_above_threshold():
    text = " ".join(f"word{i}" for i in range(50_000))
    msgs = [Message.user(text)]
    assert should_compact(msgs, model="anthropic/claude-sonnet-4-6", threshold=0.7) is True


def test_compact_preserves_recent():
    msgs = [Message.user(f"msg {i}") for i in range(20)]
    compacted = compact_messages(msgs, keep_recent=3)
    assert len(compacted) <= 5  # summary + 3 recent


def test_compact_small_history_unchanged():
    msgs = [Message.user("a"), Message.user("b")]
    assert compact_messages(msgs, keep_recent=5) == msgs


def test_compact_marks_summary():
    msgs = [Message.user(f"msg {i}") for i in range(10)]
    compacted = compact_messages(msgs, keep_recent=2)
    assert compacted[0].role.value == "system"
    assert "compacted" in compacted[0].text.lower()


def test_system_prompt_survives_compaction():
    """The system prompt (with skills) must not be dropped — it used to
    be silently lost when keep_recent was smaller than its position."""
    msgs = [
        Message.system("You are eaccode. Skills: ## git-workflow ..."),
        *[Message.user(f"msg {i}") for i in range(10)],
    ]
    compacted = compact_messages(msgs, keep_recent=3)
    assert compacted[0].role.value == "system"
    assert "eaccode" in compacted[0].text


def test_soft_tail_keeps_residues():
    msgs = [Message.user("hello world"), Message.assistant("hi there"),
            *[Message.user(f"msg {i}") for i in range(8)]]
    compacted = compact_messages(msgs, keep_recent=2)
    summary = compacted[0].text
    assert "hello world" in summary      # demoted, not dropped
    assert "[user]" in summary and "[assistant]" in summary


def test_soft_tail_redacts_tool_payloads():
    msgs = [
        Message.assistant_with_tool_calls(
            [TextContent(text="checking")],
            [ToolCall(id="t1", name="read",
                      arguments={"path": "/etc/secret.conf"})],
        ),
        *[Message.user(f"msg {i}") for i in range(9)],
    ]
    compacted = compact_messages(msgs, keep_recent=2)
    summary = compacted[0].text
    assert "read" in summary             # tool name kept
    assert "/etc/secret.conf" not in summary  # args redacted (P0.2)
    assert "args redacted" in summary


def test_ghost_skill_defense_leaves_markers():
    """An oversized system prompt loses skill sections but keeps markers."""
    skills = "\n## ".join(
        [f"skill-{i}: " + "x" * 4000 for i in range(40)]
    )
    system = Message.system("You are eaccode.\n## " + skills)
    msgs = [system, *[Message.user(f"msg {i}") for i in range(12)]]
    compacted = compact_messages(msgs, keep_recent=3, model="minimax/MiniMax-M3")
    head = compacted[0].text
    if "Ghost skills" in head:
        assert GHOST_MARKER in head
        assert "skill_view" in head
    # The head must stay inside the system budget (25% of 200k).
    from eaccode.llm.tokens import count_message_tokens

    assert count_message_tokens([compacted[0]], "minimax/MiniMax-M3") <= 50_000


def test_feasibility_skip_avoids_llm_call():
    """A tiny middle must not trigger the summarize callable."""
    calls = []
    msgs = [Message.user(f"msg {i}") for i in range(12)]

    def summarize(middle):
        calls.append(middle)
        return "LLM SUMMARY"

    compacted = compact_messages(
        msgs, keep_recent=4, summarize=summarize, model="minimax/MiniMax-M3",
        threshold=0.7,
    )
    # Middle is tiny relative to the 200k budget → feasibility skip.
    assert calls == []
    assert "LLM SUMMARY" not in compacted[0].text


def test_feasibility_skip_runs_for_large_middle():
    calls = []
    big = " ".join(f"word{i}" for i in range(20_000))  # ~30k+ tokens
    msgs = [Message.user(big), *[Message.user(f"msg {i}") for i in range(6)]]

    def summarize(middle):
        calls.append(middle)
        return "LLM SUMMARY"

    compacted = compact_messages(
        msgs, keep_recent=3, summarize=summarize,
        model="anthropic/claude-sonnet-4-6", threshold=0.7,
    )
    assert calls == [msgs[:-3]]
    assert "LLM SUMMARY" in compacted[0].text


def test_effective_threshold_small_window_floor():
    # <512K window (deepseek: 128K) → floor at 50%
    assert effective_threshold("deepseek/deepseek-chat", 0.7) == 0.5
    assert effective_threshold("deepseek/deepseek-chat", 0.3) == 0.3
    # 200K is below 512K too — MiniMax gets the floor as well
    assert effective_threshold("minimax/MiniMax-M3", 0.7) == 0.5
    # >= 512K windows keep the user threshold
    assert effective_threshold("gemini/gemini-2.5-pro", 0.7) == 0.7


def test_small_window_compacts_earlier():
    # ~90K tokens of distinct words: over deepseek's 50% floor (64K of
    # 128K), far under gemini's 70% of 1M.
    text = " ".join(f"word{i}" for i in range(30_000))
    msgs = [Message.user(text)]
    assert should_compact(msgs, model="deepseek/deepseek-chat", threshold=0.7) is True
    assert should_compact(msgs, model="gemini/gemini-2.5-pro", threshold=0.7) is False
