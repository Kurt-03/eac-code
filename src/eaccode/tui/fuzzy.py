"""Description-aware fuzzy scoring for the slash-command menu.

Ported from Hermes ui-tui/src/app/slash/fuzzyScore.ts (which itself
follows superagent-ai/grok-cli): candidates are scored in tiers —
exact match on id/label/alias (0), prefix (1), substring (2) — and the
description text is tokenized and matched at a +3 offset (exact word
3, word prefix 4, word substring 5). Lower score wins; None means no
match. An empty query returns the list untouched.
"""

from __future__ import annotations

import re

_WORD_SPLIT = re.compile(r"[^a-z0-9]+")


def tokenize_search_text(value: str) -> list[str]:
    normalized = value.lower()
    return [normalized, *[t for t in _WORD_SPLIT.split(normalized) if t]]


def normalize_slash_query(query: str) -> str:
    return query.strip().lstrip("/").lower()


def _score_fields(fields: list[str], query: str, offset: int) -> float:
    for field in fields:
        if field == query or f"/{field}" == query:
            return offset
    for field in fields:
        if field.startswith(query) or f"/{field}".startswith(query):
            return offset + 1
    for field in fields:
        if query in field:
            return offset + 2
    return float("inf")


def score_slash_item(item: dict, query: str) -> float:
    """Score one item dict {name, description, aliases} — lower is better."""
    command_fields = tokenize_search_text(
        " ".join([item.get("name", ""), item.get("label", ""),
                  *item.get("aliases", [])])
    )
    description_fields = tokenize_search_text(item.get("description", ""))
    return min(
        _score_fields(command_fields, query, 0),
        _score_fields(description_fields, query, 3),
    )


def rank_slash_items(items: list[dict], query: str) -> list[dict]:
    """Filter + stable-sort *items* by fuzzy score against *query*."""
    normalized = normalize_slash_query(query)
    if not normalized:
        return list(items)
    scored = []
    for index, item in enumerate(items):
        score = score_slash_item(item, normalized)
        if score != float("inf"):
            scored.append((score, index, item))
    scored.sort(key=lambda entry: (entry[0], entry[1]))
    return [item for _, _, item in scored]
