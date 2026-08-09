"""Tests for the stateful streaming think-scrubber (Phase H.1)."""

from eaccode.llm.think_scrubber import StreamingThinkScrubber


def test_think_split_across_deltas_is_scrubbed():
    s = StreamingThinkScrubber()
    assert s.feed("<thi") == ""
    assert s.feed("nk>secret plan") == ""
    assert s.feed("</think>visible") == "visible"


def test_full_block_in_one_delta():
    s = StreamingThinkScrubber()
    assert s.feed("<think>hidden</think>shown") == "shown"


def test_multiple_blocks():
    s = StreamingThinkScrubber()
    out = s.feed("a<think>x</think>b<reasoning>y</reasoning>c")
    assert out == "abc"


def test_unterminated_block_swallows_rest():
    s = StreamingThinkScrubber()
    # Open tag at a BLOCK BOUNDARY (start of stream) → block swallows all.
    assert s.feed("<think>never closes") == ""
    assert s.feed("more hidden") == ""
    # Mid-line open is NOT a boundary → kept as prose (Hermes semantics).
    s2 = StreamingThinkScrubber()
    assert s2.feed("before<think>midline") == "before<think>midline"


def test_boundary_gating_keeps_inline_mentions():
    """Prose mentioning '<think>' mid-line must NOT be stripped."""
    s = StreamingThinkScrubber()
    out = s.feed("the <think> tag is a marker")
    assert "think" in out  # inline mention survives (no boundary)


def test_orphan_close_tags_removed():
    s = StreamingThinkScrubber()
    out = s.feed("</think>text")  # orphan close at start
    assert out == "text"


def test_reset_clears_state():
    s = StreamingThinkScrubber()
    s.feed("x<think>hidden")
    s.reset()
    assert s.feed("fresh") == "fresh"


def test_reasoning_scratchpad_tag():
    s = StreamingThinkScrubber()
    assert s.feed("<REASONING_SCRATCHPAD>deep thoughts</REASONING_SCRATCHPAD>out") == "out"


def test_thinking_variant():
    s = StreamingThinkScrubber()
    assert s.feed("<thinking>h</thinking>") == ""
    assert s.feed("after") == "after"


def test_empty_and_none_deltas():
    s = StreamingThinkScrubber()
    assert s.feed("") == ""
    assert s.feed("plain") == "plain"
