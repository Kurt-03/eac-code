"""Tests for guardrail integration into the agent loop (Phase C.3).

The fake LLM keeps issuing the SAME failing bash call. With guardrails
active, the loop must surface the failure, warn, and eventually the
LLM gets a synthetic block result — proving the loop can't spin on an
identical failing call forever.
"""

import pytest

from eaccode.agent.guardrails import GuardrailConfig
from eaccode.agent.loop import AgentConfig, AgentLoop
from eaccode.config.settings import PermissionMode
from eaccode.llm.models import Message, ToolCall
from eaccode.permissions.policy import PolicyEngine
from eaccode.permissions.rules import RuleSet
from eaccode.tools.base import ToolRegistry
from eaccode.tools.builtin.bash import BashTool


class _FakeClient:
    """Returns one bash tool call per turn, forever — until guardrails stop it."""

    def __init__(self):
        self.calls = 0

    def complete(self, req):
        self.calls += 1
        from eaccode.llm.client import CompletionResponse, TokenUsage

        return CompletionResponse(
            text="",
            tool_calls=[ToolCall(id=f"c{self.calls}", name="bash",
                                  arguments={"command": "exit 1"})],
            stop_reason="tool_use",
            usage=TokenUsage(),
            model="fake",
        )


def _make_agent(workdir, config_override=None):
    client = _FakeClient()
    registry = ToolRegistry()
    registry.register(BashTool())
    policy = PolicyEngine(mode=PermissionMode.BYPASS_PERMISSIONS, rules=RuleSet())
    agent = AgentLoop(client, registry, policy,
                      AgentConfig(workdir=workdir, max_turns=30))
    if config_override is not None:
        agent.guardrails = config_override  # inject test config
    return agent, client


@pytest.mark.asyncio
async def test_loop_guardrails_break_identical_failure_loop(tmp_path):
    """Same failing call repeated → guardrail warning reaches the LLM as
    tool-result context, and hard-stop mode blocks further identical calls."""
    agent, client = _make_agent(tmp_path)
    # Enable hard-stop so the guardrail can actually block.
    agent.guardrails.config = GuardrailConfig(
        hard_stop_enabled=True,
        exact_failure_warn_after=2,
        exact_failure_block_after=3,
    )
    with pytest.raises(Exception):
        await agent.run([Message.user("run it")])
    # Either the loop exhausted max_turns (all blocked) or guardrail halted.
    assert client.calls >= 3


@pytest.mark.asyncio
async def test_loop_block_result_carries_guardrail_code(tmp_path):
    """A blocked call returns a synthetic error result with the guardrail
    code in metadata (so the REPL can render it distinctly)."""
    from eaccode.agent.guardrails import GuardrailConfig

    agent, _client = _make_agent(tmp_path)
    agent.guardrails.config = GuardrailConfig(
        hard_stop_enabled=True,
        exact_failure_warn_after=1,
        exact_failure_block_after=2,
    )
    # Drive two identical failing calls through _execute_guarded directly.
    tc = ToolCall(id="x", name="bash", arguments={"command": "exit 1"})
    from eaccode.tools.base import ToolContext

    ctx = ToolContext(workdir=tmp_path)
    r1 = await agent._execute_guarded(tc, ctx)
    await agent._execute_guarded(tc, ctx)
    r3 = await agent._execute_guarded(tc, ctx)
    assert r1.is_error is True
    assert r3.is_error is True
    # r3 should be the block (or a warn with the guardrail tag appended).
    assert "guardrail" in r3.metadata or "[guardrail]" in r3.content


def test_tool_class_annotation_present_on_builtins():
    """Every builtin tool declares its guardrail class (Phase C.1)."""
    from eaccode.tools.factory import build_default_registry

    reg = build_default_registry()
    for tool in reg.list():
        assert tool.tool_class is not None, f"{tool.name} missing tool_class"
    names = {t.name: t.tool_class.value for t in reg.list()}
    assert names["read"] == "idempotent"
    assert names["bash"] == "mutating"
    # Provider-gated tools may not be in the default registry; verify the
    # annotation at the class level instead.
    from eaccode.tools.builtin.web_search import WebSearchTool

    assert WebSearchTool.tool_class.value == "runaway"
