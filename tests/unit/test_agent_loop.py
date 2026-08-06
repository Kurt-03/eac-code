"""Tests for the core agent loop (Task 5.1)."""

import pytest

from eaccode.agent.loop import AgentConfig, AgentLoop, MaxTurnsExceededError
from eaccode.config.settings import PermissionMode
from eaccode.llm.client import CompletionRequest, CompletionResponse, TokenUsage
from eaccode.llm.models import Message, ToolCall
from eaccode.permissions.policy import PolicyEngine
from eaccode.permissions.rules import RuleSet
from eaccode.tools.base import ToolRegistry
from eaccode.tools.builtin.read import ReadTool


class MockClient:
    """Stands in for LLMClient.complete — scripted responses."""

    def __init__(self, responses: list[CompletionResponse]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def complete(self, req: CompletionRequest) -> CompletionResponse:
        resp = self.responses[self.calls]
        self.calls += 1
        return resp


def _tool_response(tool_call: ToolCall) -> CompletionResponse:
    return CompletionResponse(
        text="",
        tool_calls=[tool_call],
        stop_reason="tool_use",
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        model="minimax/MiniMax-M3",
    )


def _final_response(text: str) -> CompletionResponse:
    return CompletionResponse(
        text=text,
        tool_calls=[],
        stop_reason="stop",
        usage=TokenUsage(input_tokens=20, output_tokens=10),
        model="minimax/MiniMax-M3",
    )


@pytest.mark.asyncio
async def test_agent_loop_handles_tool_call_then_final(tmp_path):
    client = MockClient([
        _tool_response(ToolCall(id="t1", name="read", arguments={"path": "x.txt"})),
        _final_response("All done!"),
    ])
    reg = ToolRegistry()
    reg.register(ReadTool())
    policy = PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet())
    agent = AgentLoop(client, reg, policy, AgentConfig(workdir=tmp_path))
    (tmp_path / "x.txt").write_text("content")
    result = await agent.run([Message.user("read x.txt")])
    assert result.final_text == "All done!"
    assert client.calls == 2
    # the tool result must be in the message history for the LLM
    tool_msgs = [m for m in result.messages if m.role.value == "tool"]
    assert len(tool_msgs) == 1
    assert "content" in tool_msgs[0].text


@pytest.mark.asyncio
async def test_agent_loop_respects_max_turns(tmp_path):
    tool_resp = _tool_response(ToolCall(id="t1", name="read", arguments={"path": "x.txt"}))
    client = MockClient([tool_resp] * 100)
    reg = ToolRegistry()
    reg.register(ReadTool())
    policy = PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet())
    agent = AgentLoop(
        client, reg, policy,
        AgentConfig(workdir=tmp_path, max_turns=3),
    )
    with pytest.raises(MaxTurnsExceededError):
        await agent.run([Message.user("hi")])
    assert client.calls == 3


@pytest.mark.asyncio
async def test_agent_loop_denied_tool_reports_error_to_llm(tmp_path):
    """A denied tool call must come back to the LLM as an error result,
    so the agent can adapt instead of hanging."""
    client = MockClient([
        _tool_response(ToolCall(id="t1", name="read", arguments={"path": "x.txt"})),
        _final_response("I cannot do that."),
    ])
    reg = ToolRegistry()
    reg.register(ReadTool())
    # PLAN mode denies nothing for read... use a deny rule to force denial
    from eaccode.permissions.rules import Action, Rule
    policy = PolicyEngine(PermissionMode.DEFAULT, RuleSet(rules=(
        Rule(tool="read", action=Action.DENY, pattern="*"),
    )))
    agent = AgentLoop(client, reg, policy, AgentConfig(workdir=tmp_path))
    result = await agent.run([Message.user("read x.txt")])
    tool_msgs = [m for m in result.messages if m.role.value == "tool"]
    assert len(tool_msgs) == 1
    assert "denied" in tool_msgs[0].text.lower() or "deny" in tool_msgs[0].text.lower()


@pytest.mark.asyncio
async def test_agent_loop_usage_accumulates(tmp_path):
    client = MockClient([
        _tool_response(ToolCall(id="t1", name="read", arguments={"path": "x.txt"})),
        _final_response("done"),
    ])
    reg = ToolRegistry()
    reg.register(ReadTool())
    policy = PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet())
    agent = AgentLoop(client, reg, policy, AgentConfig(workdir=tmp_path))
    (tmp_path / "x.txt").write_text("c")
    result = await agent.run([Message.user("go")])
    assert result.turns == 2
    assert result.usage.input_tokens == 30
    assert result.usage.output_tokens == 15
