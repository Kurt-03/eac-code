"""Tests for the background review (C.2) — parsing + whitelisted agent."""

import pytest

from eaccode.agent.background_review import (
    REVIEW_WHITELIST,
    parse_review_output,
    run_review,
)
from eaccode.agent.loop import AgentConfig, AgentResult
from eaccode.llm.client import TokenUsage


def test_parse_empty():
    result = parse_review_output("no json here")
    assert result.empty
    assert result.raw_text == "no json here"


def test_parse_facts_and_skills():
    text = ('```json\n{"facts": ["use uv", "tests need no:cacheprovider", ""], '
            '"skills": ["tdd: follow red-green"]}\n```')
    result = parse_review_output(text)
    assert result.facts == ["use uv", "tests need no:cacheprovider"]
    assert result.skills == ["tdd: follow red-green"]


def test_parse_caps():
    text = '{"facts": ["a", "b", "c", "d", "e", "f"], "skills": ["x", "y", "z"]}'
    result = parse_review_output(text)
    assert len(result.facts) <= 4
    assert len(result.skills) <= 2


def test_whitelist_only_memory_and_skills():
    assert set(REVIEW_WHITELIST) == {"memory_*", "skill_*"}


@pytest.mark.asyncio
async def test_run_review_uses_whitelist_and_returns_parsed(tmp_path):
    captured = {}

    class FakeSubAgent:
        config = AgentConfig(workdir=tmp_path)

        async def run(self, messages):
            captured["prompt"] = messages[-1].text
            return AgentResult(
                final_text='{"facts": ["proj uses uv"], "skills": []}',
                messages=[], usage=TokenUsage(), turns=1, cost_usd=0.0,
            )

    async def fake_builder(workdir, max_turns=15, allowed_tools=None):
        captured["allowed_tools"] = allowed_tools
        return FakeSubAgent(), None, None

    result = await run_review(fake_builder, tmp_path, "session summary")
    assert result.facts == ["proj uses uv"]
    assert captured["allowed_tools"] == ["memory_*", "skill_*"]
    assert "background reviewer" in captured["prompt"]


@pytest.mark.asyncio
async def test_run_review_never_raises(tmp_path):
    async def broken_builder(workdir, max_turns=15, allowed_tools=None):
        raise RuntimeError("no provider")

    result = await run_review(broken_builder, tmp_path, "summary")
    assert result.empty


def test_review_whitelist_filters_registry():
    """The wildcard whitelist really restricts the default registry."""
    from eaccode.tools.factory import build_default_registry

    reg = build_default_registry(allowed_tools=["memory_*", "skill_*"])
    names = {t.name for t in reg.list()}
    assert names <= {"memory_remember", "memory_recall", "memory_forget",
                     "memory_edit", "skill_create", "skill_patch",
                     "skill_list", "skill_delete", "skill_write_file",
                     "skill_remove_file"}
    assert "bash" not in names
    assert "write" not in names
