"""Tests for runtime helpers (F.7-F.14)."""

import time

from eaccode.agent.runtime_helpers import (
    IterationBudget,
    TurnRetryState,
    extract_text,
    is_final_response,
    merge_usage,
)
from eaccode.llm.client import TokenUsage


def test_is_final_response():
    assert is_final_response("done") is True
    assert is_final_response("   ") is False
    assert is_final_response("") is False


def test_extract_text_variants():
    assert extract_text(None) == ""
    assert extract_text("plain") == "plain"
    assert extract_text([{"type": "text", "text": "a"}, {"type": "tool_use",
                                                         "name": "bash"}]) == "a [tool: bash]"
    assert extract_text({"weird": 1}) == "{'weird': 1}"


def test_merge_usage():
    a = TokenUsage(input_tokens=10, output_tokens=5, cost_usd=0.01)
    b = TokenUsage(input_tokens=2, output_tokens=3, cost_usd=0.02)
    merged = merge_usage(a, b)
    assert merged.input_tokens == 12
    assert merged.output_tokens == 8
    assert abs(merged.cost_usd - 0.03) < 1e-9
    assert merge_usage(None, b) is b
    assert merge_usage(a, None) is a


def test_iteration_budget_turns():
    budget = IterationBudget(max_turns=3)
    assert budget.exhausted(0, 0) is False
    assert budget.exhausted(3, 0) is True
    assert budget.remaining(1, 0) == 2


def test_iteration_budget_tokens():
    budget = IterationBudget(max_turns=30, max_tokens=100)
    assert budget.exhausted(0, 99) is False
    assert budget.exhausted(0, 100) is True


def test_iteration_budget_deadline():
    budget = IterationBudget(max_turns=30, deadline=time.time() - 5)
    assert budget.exhausted(0, 0) is True


def test_turn_retry_state():
    state = TurnRetryState(max_retries=2)
    assert state.exhausted is False
    state.record_failure("boom")
    state.record_failure("boom again")
    assert state.exhausted is True
    assert "boom again" in state.last_error
