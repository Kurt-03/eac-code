"""Skill triggers + pre-filter (A.6) — frontmatter trigger matching.

Skills declare ``triggers: [keyword, ...]`` in their frontmatter. When a
user prompt contains a trigger word, the skill is injected into the turn
context (Hermes-style dynamic loading). The pre-filter caps how many
skills enter a turn: triggered skills first, then recency, then nothing.

``fuzzy_match`` uses difflib (stdlib) — no new dependency.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from eaccode.memory.skills import Skill

MAX_TURN_SKILLS = 6  # hard cap for dynamic injection per turn
FUZZY_CUTOFF = 0.6


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-zäöüß0-9][a-zäöüß0-9\-]{2,}", text.lower()))


def match_triggers(skills: list[Skill], text: str) -> list[Skill]:
    """Skills whose triggers appear in *text* (case-insensitive)."""
    words = _words(text)
    hits = []
    for s in skills:
        for t in s.triggers:
            key = t.lower()
            if key in words or key in text.lower():
                hits.append(s)
                break
    return hits


def fuzzy_match(word: str, candidates: list[str], cutoff: float = FUZZY_CUTOFF) -> str | None:
    """Best fuzzy candidate for *word* (skill names/triggers)."""
    best, best_ratio = None, cutoff
    for c in candidates:
        ratio = SequenceMatcher(None, word.lower(), c.lower()).ratio()
        if ratio > best_ratio:
            best, best_ratio = c, ratio
    return best


def select_skills_for_turn(
    skills: list[Skill],
    text: str,
    max_inject: int = MAX_TURN_SKILLS,
) -> list[Skill]:
    """Triggered skills first, then most-recently-used, capped at max."""
    triggered = match_triggers(skills, text)
    remaining = [s for s in skills if s not in triggered]
    remaining.sort(key=lambda s: s.last_used or s.source.stat().st_mtime,
                   reverse=True)
    return triggered[:max_inject] + remaining[: max(0, max_inject - len(triggered))]


def build_skill_index(skills: list[Skill]) -> str:
    """Compact name+description index (for large skill sets)."""
    if not skills:
        return ""
    lines = ["# Available Skills (index)", ""]
    for s in skills:
        line = f"- **{s.name}**"
        if s.description:
            line += f": {s.description}"
        lines.append(line)
    return "\n".join(lines)
