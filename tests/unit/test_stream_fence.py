"""Tests for the stream single-writer fence (Phase C.4)."""

from eaccode.llm.stream_fence import (
    claim_stream_writer,
    fence_delta,
    stream_writer_is_current,
)


class FakeOwner:
    def __init__(self):
        self._stream_writer_token = 0


def test_claim_returns_increasing_tokens():
    o1, o2 = FakeOwner(), FakeOwner()
    t1 = claim_stream_writer(o1)
    t2 = claim_stream_writer(o2)
    assert t1 != t2


def test_current_writer_passes_deltas():
    o = FakeOwner()
    token = claim_stream_writer(o)
    o._stream_writer_token = token
    assert stream_writer_is_current(o, token) is True
    assert fence_delta(o, token, "hello") == "hello"


def test_stale_writer_drops_deltas():
    o = FakeOwner()
    old_token = claim_stream_writer(o)
    # A new turn claims the writer, bumping the token.
    new_token = claim_stream_writer(o)
    o._stream_writer_token = new_token
    assert stream_writer_is_current(o, old_token) is False
    assert fence_delta(o, old_token, "stale chunk") is None


def test_falsy_token_never_fenced():
    """A token of 0 (no-op claim) must never fence — best-effort guard."""
    o = FakeOwner()
    o._stream_writer_token = 0
    assert stream_writer_is_current(o, 0) is True
    assert fence_delta(o, 0, "data") == "data"
