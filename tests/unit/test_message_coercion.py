"""P7 (v0.7.2 followup): classic REPL feeds dicts; agent.run() must accept them.

Regression: bare `eaccode` then `hi` produced
'AttributeError: dict object has no attribute role'
because the legacy loop code expected Message objects with .role
attribute access.
"""

import asyncio


def test_coerce_messages_passthrough_for_messages_objects():
    """Already-Message lists pass through with the same content."""
    from eaccode.agent.loop import AgentLoop
    from eaccode.llm.models import Message

    msgs = [Message.user("hi"), Message.assistant("hello")]
    out = AgentLoop._coerce_messages(msgs)
    # Same content, new list (the function rebuilds for safety).
    assert [m.role.value for m in out] == ["user", "assistant"]
    assert out[0].text == "hi"
    assert out[1].text == "hello"


def test_agent_run_coerces_dict_messages_at_boundary(tmp_path):
    """Regression: bare `eaccode` then `hi` produced
    'AttributeError: dict object has no attribute role' because the
    legacy loop code expected Message objects with .role attribute access.

    Verify the fix at the boundary: passing dicts to agent.run() must
    not crash, even when the agent eventually reaches the LLM. We stop
    short of a real LLM call by using a stub client.
    """

    from eaccode.llm.client import CompletionResponse, TokenUsage
    from eaccode.llm.models import Message

    class _StubClient:
        def __init__(self, *a, **kw):
            self.default_model = "MiniMax-M3"
            self.provider_name = "minimax"
            self.calls = 0

        def complete(self, req):
            self.calls += 1
            return CompletionResponse(
                text="OK", tool_calls=[], usage=TokenUsage(),
                stop_reason="stop", model="stub-model",
            )

    from eaccode.agent import loop as loop_mod

    # Build an AgentLoop with the stub client (no async init needed).
    from eaccode.config.settings import PermissionMode
    from eaccode.permissions.policy import PolicyEngine
    from eaccode.permissions.rules import RuleSet
    from eaccode.tools.base import ToolRegistry

    cfg = loop_mod.AgentConfig(workdir=tmp_path, max_turns=1)
    # AgentLoop expects a ToolRegistry (it wraps it in ToolExecutor
    # internally — check the constructor).
    agent = loop_mod.AgentLoop(
        client=_StubClient(),
        tools=ToolRegistry(),
        policy=PolicyEngine(mode=PermissionMode.DEFAULT, rules=RuleSet()),
        config=cfg,
    )

    # Dict input — the classic REPL shape. No AttributeError now.
    result = asyncio.run(agent.run([{"role": "user", "content": "hi"}]))
    assert isinstance(result, loop_mod.AgentResult)
    assert all(isinstance(m, Message) for m in result.messages)
    assert result.messages[0].role.value == "user"


def test_coerce_messages_handles_dicts():
    from eaccode.agent.loop import AgentLoop

    out = AgentLoop._coerce_messages([
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "system", "content": "rules"},
        {"role": "tool", "tool_call_id": "x", "content": "result"},
    ])
    assert [m.role.value for m in out] == ["user", "assistant", "system", "tool"]
    assert out[0].text == "hi"
    assert out[3].tool_call_id == "x"


def test_coerce_messages_stringifies_non_dict():
    from eaccode.agent.loop import AgentLoop

    out = AgentLoop._coerce_messages(["raw text"])
    assert out[0].role.value == "user"
    assert out[0].text == "raw text"
