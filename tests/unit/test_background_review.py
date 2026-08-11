"""Tests for the background review (C.2) — parsing + whitelisted agent."""

import pytest
from pydantic import BaseModel

from eaccode.agent.background_review import (
    REVIEW_WHITELIST,
    parse_review_output,
    run_review,
)
from eaccode.agent.loop import AgentConfig, AgentResult
from eaccode.llm.client import TokenUsage
from eaccode.llm.models import Message, ToolCall
from eaccode.tools.base import Tool, ToolRegistry, ToolResult


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


@pytest.mark.asyncio
async def test_turn_complete_callback_fires(tmp_path):
    """F.7: on_turn_complete receives (turn, text, usage)."""
    from eaccode.agent.loop import AgentConfig, AgentLoop
    from eaccode.config.settings import PermissionMode
    from eaccode.llm.client import CompletionResponse, TokenUsage
    from eaccode.permissions.policy import PolicyEngine
    from eaccode.permissions.rules import RuleSet
    from eaccode.tools.base import ToolRegistry

    class FakeClient:
        def complete(self, req):
            return CompletionResponse(
                text="final answer", tool_calls=[], stop_reason="end_turn",
                usage=TokenUsage(input_tokens=5, output_tokens=3),
                model="fake",
            )

    events = []

    def on_turn_complete(turn, text, usage):
        events.append((turn, text, usage.input_tokens))

    loop = AgentLoop(
        FakeClient(), ToolRegistry(),
        PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet()),
        AgentConfig(workdir=tmp_path, max_turns=3,
                    on_turn_complete=on_turn_complete),
    )
    result = await loop.run([Message.user("hi")])
    assert result.final_text == "final answer"
    assert events == [(0, "final answer", 5)]
    assert result.usage.input_tokens == 5


@pytest.mark.asyncio
async def test_runtime_cwd_flows_into_tool_context(tmp_path):
    """F.13: runtime_cwd seeds ToolContext.runtime_cwd."""
    from eaccode.agent.loop import AgentConfig, AgentLoop
    from eaccode.config.settings import PermissionMode
    from eaccode.llm.client import CompletionResponse, TokenUsage
    from eaccode.permissions.policy import PolicyEngine
    from eaccode.permissions.rules import RuleSet

    seen = {}

    class EchoInput(BaseModel):
        pass

    class EchoTool(Tool):
        name = "echo_ctx"
        description = "echo"
        input_model = EchoInput
        requires_permission = False
        tool_class = None

        async def run(self, input, ctx):
            seen["runtime_cwd"] = ctx.runtime_cwd
            return ToolResult(content="ok")

    class FakeClient:
        def __init__(self):
            self.calls = 0

        def complete(self, req):
            self.calls += 1
            if self.calls > 1:
                return CompletionResponse(
                    text="done", tool_calls=[], stop_reason="end_turn",
                    usage=TokenUsage(), model="fake",
                )
            return CompletionResponse(
                text="", tool_calls=[ToolCall(id="1", name="echo_ctx",
                                              arguments={})],
                stop_reason="tool_calls", usage=TokenUsage(), model="fake",
            )

    reg = ToolRegistry()
    reg.register(EchoTool())
    sub = tmp_path / "sub"
    sub.mkdir()
    loop = AgentLoop(
        FakeClient(), reg,
        PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet()),
        AgentConfig(workdir=tmp_path, runtime_cwd=sub, max_turns=2),
    )
    await loop.run([Message.user("go")])
    assert seen["runtime_cwd"] == sub
