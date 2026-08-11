"""Background review (C.2) — a whitelisted agent reviews the session.

Runs a dedicated agent instance whose tool whitelist is
``{memory_*, skill_*}`` — it can propose facts and skills but cannot
touch the filesystem or shell. The result is a structured list of
proposals; applying them goes through the approval registry (C.3), so a
review can never silently change anything.

The builder is injected (``build_agent_async`` in production, fakes in
tests) and must accept ``workdir`` + ``allowed_tools``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REVIEW_WHITELIST = ("memory_*", "skill_*")

REVIEW_PROMPT = (
    "You are the background reviewer. Review the session above.\n"
    "Reply with ONLY a JSON object:\n"
    '{"facts": ["<durable project fact>", ...], '
    '"skills": ["<skill-name>: <one-line description>", ...]}\n'
    "Rules:\n"
    "- facts: things learned about THIS project that future sessions need.\n"
    "- skills: only when a reusable procedure was followed (max 2).\n"
    "- Do NOT execute tools; propose only.\n"
)

_MAX_FACTS = 4
_MAX_SKILLS = 2


@dataclass
class ReviewResult:
    facts: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def empty(self) -> bool:
        return not self.facts and not self.skills


def parse_review_output(text: str) -> ReviewResult:
    """Tolerant JSON extraction of {facts: [...], skills: [...]}."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return ReviewResult(raw_text=text)
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return ReviewResult(raw_text=text)
    facts = [str(f).strip() for f in data.get("facts", []) if str(f).strip()]
    skills = [str(s).strip() for s in data.get("skills", []) if str(s).strip()]
    return ReviewResult(
        facts=facts[:_MAX_FACTS],
        skills=skills[:_MAX_SKILLS],
        raw_text=text,
    )


async def run_review(
    builder: Callable[..., Any],
    workdir: Path,
    session_summary: str,
    max_turns: int = 3,
) -> ReviewResult:
    """Run one review pass over *session_summary*; never raises."""
    from eaccode.llm.models import Message

    try:
        agent, _, _ = await builder(
            workdir,
            max_turns=max_turns,
            allowed_tools=list(REVIEW_WHITELIST),
        )
        prompt = f"{session_summary}\n\n{REVIEW_PROMPT}"
        result = await agent.run([Message.user(prompt)])
        return parse_review_output(result.final_text or "")
    except Exception:
        return ReviewResult()
