"""Tests for the streaming agent loop (Task 7.3)."""
from pathlib import Path

import pytest

from eaccode.agent.loop import AgentConfig, AgentLoop
from eaccode.config.settings import PermissionMode
from eaccode.llm.client import CompletionRequest, ReasoningDelta, TokenUsage
from eaccode.llm.models import Message, ToolCall
from eaccode.permissions.policy import PolicyEngine
from eaccode.permissions.rules import RuleSet
from eaccode.tools.base import ToolRegistry
from eaccode.tools.builtin.read import ReadTool


class StreamingMockClient:
    """Scripted stream() responses: text deltas → tool call → final text."""

    def __init__(self) -> None:
        self.calls = 0
        self.usage = TokenUsage(input_tokens=10, output_tokens=5, cost_usd=0.01)

    async def stream(self, req: CompletionRequest):
        if self.calls == 0:
            yield "Let me "
            yield "read the file."
            yield ToolCall(id="t1", name="read", arguments={"path": "x.txt"})
        else:
            yield "Final "
            yield "answer!"
        self.calls += 1


@pytest.mark.asyncio
async def test_run_streaming_text_and_tools(tmp_path):
    client = StreamingMockClient()
    reg = ToolRegistry()
    reg.register(ReadTool())
    policy = PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet())
    agent = AgentLoop(client, reg, policy, AgentConfig(workdir=tmp_path))
    (tmp_path / "x.txt").write_text("content")

    deltas: list[str] = []
    tool_calls: list[ToolCall] = []
    result = await agent.run_streaming(
        [Message.user("read x.txt")],
        on_text_delta=lambda d: deltas.append(d),
        on_tool_call=lambda tc: tool_calls.append(tc),
    )
    assert result.final_text == "Final answer!"
    assert "".join(deltas) == "Let me read the file.Final answer!"
    assert [tc.name for tc in tool_calls] == ["read"]
    assert client.calls == 2
    # the tool result reached the LLM history
    tool_msgs = [m for m in result.messages if m.role.value == "tool"]
    assert len(tool_msgs) == 1
    assert "content" in tool_msgs[0].text


@pytest.mark.asyncio
async def test_run_streaming_reasoning_deltas_separate(tmp_path):
    class WithReasoning(StreamingMockClient):
        async def stream(self, req):
            yield ReasoningDelta("thinking hard...")
            async for chunk in super().stream(req):
                yield chunk

    reg = ToolRegistry()
    reg.register(ReadTool())
    policy = PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet())
    agent = AgentLoop(WithReasoning(), reg, policy, AgentConfig(workdir=tmp_path))
    (tmp_path / "x.txt").write_text("c")

    reasoning: list[str] = []
    deltas: list[str] = []
    await agent.run_streaming(
        [Message.user("go")],
        on_text_delta=lambda d: deltas.append(d),
        on_reasoning_delta=lambda d: reasoning.append(d),
    )
    # both turns emit reasoning (like DeepSeek) — always delivered separately
    assert reasoning == ["thinking hard...", "thinking hard..."]
    assert "thinking" not in "".join(deltas)  # reasoning nie im Antworttext


@pytest.mark.asyncio
async def test_run_streaming_respects_max_turns(tmp_path):
    class Infinite(StreamingMockClient):
        async def stream(self, req):
            yield ToolCall(id="t1", name="read", arguments={"path": "x.txt"})

    from eaccode.agent.loop import MaxTurnsExceededError

    reg = ToolRegistry()
    reg.register(ReadTool())
    policy = PolicyEngine(PermissionMode.BYPASS_PERMISSIONS, RuleSet())
    agent = AgentLoop(
        Infinite(), reg, policy, AgentConfig(workdir=tmp_path, max_turns=3)
    )
    with pytest.raises(MaxTurnsExceededError):
        await agent.run_streaming([Message.user("hi")])
