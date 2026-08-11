"""Tests for the background-review scheduler (C.1)."""

from eaccode.agent.review_scheduler import ReviewScheduler


def test_disabled_by_zero():
    scheduler = ReviewScheduler(every_turns=0)
    assert scheduler.enabled is False
    assert scheduler.should_review(10) is False


def test_window_reached_after_accumulated_turns():
    scheduler = ReviewScheduler(every_turns=5)
    assert scheduler.should_review(3) is False
    assert scheduler.should_review(2) is True  # 3 + 2 = 5
    assert scheduler.should_review(1) is False  # window reset


def test_single_turn_can_cross_window():
    scheduler = ReviewScheduler(every_turns=3)
    assert scheduler.should_review(7) is True
    assert scheduler.should_review(0) is False


def test_reset_clears_counter():
    scheduler = ReviewScheduler(every_turns=3)
    scheduler.should_review(2)
    scheduler.reset()
    assert scheduler.should_review(1) is False
