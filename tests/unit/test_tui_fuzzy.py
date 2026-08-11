"""Tests for the fuzzy slash scoring (ported from Hermes fuzzyScore.ts)."""

from eaccode.tui.fuzzy import (
    normalize_slash_query,
    rank_slash_items,
    score_slash_item,
)

_ITEMS = [
    {"name": "help", "description": "Show all commands"},
    {"name": "history", "description": "View conversation history"},
    {"name": "model", "description": "Switch model / provider"},
    {"name": "mode", "description": "Change permission mode"},
    {"name": "memory", "description": "Inspect markdown memory"},
]


def test_normalize_query():
    assert normalize_slash_query("/Model ") == "model"
    assert normalize_slash_query("//help") == "help"
    assert normalize_slash_query("") == ""


def test_exact_match_scores_zero():
    assert score_slash_item({"name": "model", "description": "x"}, "model") == 0


def test_prefix_scores_one():
    assert score_slash_item({"name": "model", "description": "x"}, "mod") == 1


def test_substring_scores_two():
    assert score_slash_item({"name": "model", "description": "x"}, "ode") == 2


def test_description_match_offset_three():
    # "history" is not matched by "conversation", but the description
    # contains the word — tier 3 (exact word in description).
    score = score_slash_item(
        {"name": "history", "description": "View conversation history"},
        "conversation",
    )
    assert score == 3


def test_no_match_is_inf():
    assert score_slash_item(
        {"name": "model", "description": "x"}, "zzz"
    ) == float("inf")


def test_rank_sorts_by_score():
    ranked = rank_slash_items(_ITEMS, "mo")
    names = [i["name"] for i in ranked]
    # model(2), mode(3), memory(4) all prefix-match "mo" with score 1 —
    # stable sort keeps original index order.
    assert names[0] == "model"
    assert names[1] == "mode"


def test_rank_empty_query_returns_all():
    ranked = rank_slash_items(_ITEMS, "")
    assert len(ranked) == len(_ITEMS)


def test_rank_filters_nonmatches():
    ranked = rank_slash_items(_ITEMS, "zzz")
    assert ranked == []


def test_rank_description_match():
    ranked = rank_slash_items(_ITEMS, "permission")
    names = [i["name"] for i in ranked]
    assert "mode" in names  # description mentions permission mode
