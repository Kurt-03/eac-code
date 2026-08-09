"""Core agent loop (Task 5.1).

Tool-calling iteration: prompt → LLM → tool calls → permission gate →
execute → results back to LLM → repeat until final answer or max_turns.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from eaccode.llm.client import (
    CompletionRequest,
    LLMClient,
    ReasoningDelta,
    StreamUsage,
    TokenUsage,
)
from eaccode.llm.models import Message, TextContent, ToolCall
from eaccode.permissions.policy import PolicyEngine
from eaccode.permissions.prompts import prompt_for_permission
from eaccode.permissions.rules import Rule
from eaccode.tools.base import ToolContext, ToolRegistry
from eaccode.tools.executor import ToolExecutor


class MaxTurnsExceededError(Exception):
    """Raised when the loop hits max_turns without a final answer."""


@dataclass
class AgentConfig:
    workdir: Path
    max_turns: int = 50
    max_budget_usd: float | None = None
    system_prompt: str | None = None
    skills_dir: Path | None = None
    on_tool_call: Callable[[ToolCall], None] | None = None
    on_tool_result: Callable[[ToolCall, object], None] | None = None
    on_text_delta: Callable[[str], None] | None = None
    on_reasoning_delta: Callable[[str], None] | None = None
    # Phase B.1: async permission ask —
    # callable(tool_name, arguments, question) -> Future[PermissionChoice].
    # When None, the sync click.confirm path (or headless deny) is used.
    ask_async: Callable[[str, dict, str], object] | None = None


@dataclass
class AgentResult:
    final_text: str
    messages: list[Message]
    usage: TokenUsage
    turns: int
    cost_usd: float


class AgentLoop:
    def __init__(
        self,
        client: LLMClient,
        tools: ToolRegistry,
        policy: PolicyEngine,
        config: AgentConfig,
    ) -> None:
        self.client = client
        self.executor = ToolExecutor(tools)
        self.policy = policy
        self.config = config
        self.session_rules: list[Rule] = []  # "always allow" patterns from prompts
        # Phase C.2/C.3: loop guardrails (reset per run).
        from eaccode.agent.guardrails import ToolCallGuardrailController

        self.guardrails = ToolCallGuardrailController()

    async def run(self, messages: list[Message]) -> AgentResult:
        # Phase H.3: expand @-references in the LAST user message before
        # the LLM sees it (earlier turns were already expanded).
        messages = self._expand_user_references(messages)
        tool_schemas = self.executor.registry.schemas()
        ctx = ToolContext(
            workdir=self.config.workdir,
            permission_mode=self.policy.mode.value,
            skills_dir=self.config.skills_dir or Path(),
        )
        total_usage = TokenUsage()

        self.guardrails.reset_for_turn()

        for turn in range(self.config.max_turns):
            req = CompletionRequest(
                messages=messages,
                tools=tool_schemas,
                system=self.config.system_prompt,
                stream=False,
            )
            resp = self.client.complete(req)
            total_usage += resp.usage

            if self.config.max_budget_usd and total_usage.cost_usd > self.config.max_budget_usd:
                raise RuntimeError(
                    f"Budget exceeded: ${total_usage.cost_usd:.2f} > "
                    f"${self.config.max_budget_usd}"
                )

            if not resp.tool_calls:
                messages.append(Message.assistant(resp.text))
                return AgentResult(
                    final_text=resp.text,
                    messages=messages,
                    usage=total_usage,
                    turns=turn + 1,
                    cost_usd=total_usage.cost_usd,
                )

            messages.append(
                Message.assistant_with_tool_calls(
                    [TextContent(text=resp.text)] if resp.text else [],
                    resp.tool_calls,
                )
            )

            for tc in resp.tool_calls:
                if self.config.on_tool_call:
                    self.config.on_tool_call(tc)
                result = await self._execute_guarded(tc, ctx)
                messages.append(
                    Message.tool_result(
                        tc.id, result.content, is_error=result.is_error, name=tc.name
                    )
                )
                if self.config.on_tool_result:
                    self.config.on_tool_result(tc, result)

        raise MaxTurnsExceededError(
            f"Reached max_turns={self.config.max_turns} without a final answer"
        )

    async def run_streaming(
        self,
        messages: list[Message],
        *,
        on_text_delta: Callable[[str], None] | None = None,
        on_reasoning_delta: Callable[[str], None] | None = None,
        on_tool_call: Callable[[ToolCall], None] | None = None,
        on_tool_result: Callable[[ToolCall, object], None] | None = None,
    ) -> AgentResult:
        """Streaming variant of run() (Task 7.3).

        Text deltas and reasoning deltas are delivered live via callbacks;
        tool calls are still executed with the permission gate and their
        results returned to the LLM. Streams do not report usage — the
        result usage stays zero for streaming turns.
        """
        # Phase H.3: expand @-references in the last user message.
        messages = self._expand_user_references(messages)
        tool_schemas = self.executor.registry.schemas()
        ctx = ToolContext(
            workdir=self.config.workdir,
            permission_mode=self.policy.mode.value,
            skills_dir=self.config.skills_dir or Path(),
        )
        total_usage = TokenUsage()

        for turn in range(self.config.max_turns):
            req = CompletionRequest(
                messages=messages,
                tools=tool_schemas,
                system=self.config.system_prompt,
                stream=True,
            )
            text_parts: list[str] = []
            tool_calls: list[ToolCall] = []
            async for chunk in self.client.stream(req):
                if isinstance(chunk, ReasoningDelta):
                    if on_reasoning_delta:
                        on_reasoning_delta(chunk.text)
                elif isinstance(chunk, ToolCall):
                    tool_calls.append(chunk)
                elif isinstance(chunk, StreamUsage):
                    total_usage += TokenUsage(
                        input_tokens=chunk.input_tokens,
                        output_tokens=chunk.output_tokens,
                        cost_usd=chunk.cost_usd,
                    )
                else:
                    text_parts.append(chunk)
                    if on_text_delta:
                        on_text_delta(chunk)
            text = "".join(text_parts)

            if not tool_calls:
                messages.append(Message.assistant(text))
                return AgentResult(
                    final_text=text,
                    messages=messages,
                    usage=total_usage,
                    turns=turn + 1,
                    cost_usd=total_usage.cost_usd,
                )

            messages.append(
                Message.assistant_with_tool_calls(
                    [TextContent(text=text)] if text else [], tool_calls
                )
            )
            for tc in tool_calls:
                if on_tool_call:
                    on_tool_call(tc)
                result = await self._execute_guarded(tc, ctx)
                messages.append(
                    Message.tool_result(
                        tc.id, result.content, is_error=result.is_error, name=tc.name
                    )
                )
                if on_tool_result:
                    on_tool_result(tc, result)

        raise MaxTurnsExceededError(
            f"Reached max_turns={self.config.max_turns} without a final answer"
        )

    def _expand_user_references(self, messages: list[Message]) -> list[Message]:
        """Phase H.3: expand @-references in the last user message."""
        if not messages or messages[-1].role.value != "user":
            return messages
        last = messages[-1]
        text = "".join(b.text for b in last.content if b.type == "text")
        if "@" not in text:
            return messages
        from eaccode.ui.context_refs import preprocess_context_references

        expanded = preprocess_context_references(text, cwd=self.config.workdir)
        if expanded == text:
            return messages
        # Rebuild the message with the expanded text (keep other blocks).
        from eaccode.llm.models import Message, TextContent

        new_content = [
            TextContent(text=expanded) if b.type == "text" else b
            for b in last.content
        ]
        return [*messages[:-1], Message(role=last.role, content=new_content)]

    async def _execute_guarded(self, tc: ToolCall, ctx: ToolContext):
        """Guardrails → permission → execute (Phase C.3).

        Guardrail warnings surface through ``on_tool_result`` as extra
        context (the LLM sees them and can change strategy); blocks
        short-circuit with a synthetic error result.
        """
        from eaccode.tools.base import ToolResult

        # Phase C.3: loop guardrails — before the call.
        guard = self.guardrails.before_call(tc.name, tc.arguments, registry=self.executor.registry)
        if guard.action == "block":
            return ToolResult(
                content=guard.message,
                is_error=True,
                metadata={"guardrail": guard.code},
            )

        result = await self._execute_with_permission(tc, ctx)

        # Phase C.3: loop guardrails — after the call (warn on loops).
        after = self.guardrails.after_call(
            tc.name, tc.arguments, result.content,
            failed=result.is_error,
            registry=self.executor.registry,
        )
        if after.action == "warn" and after.message:
            # Append the warning to the tool result so the LLM sees it
            # and can change strategy (Hermes' warning-guidance pattern).
            result.content = f"{result.content}\n\n[guardrail] {after.message}"
        return result

    async def _execute_with_permission(self, tc: ToolCall, ctx: ToolContext):
        decision = self.policy.decide(tc.name, tc.arguments)
        if decision.action.value == "deny":
            from eaccode.tools.base import ToolResult

            return ToolResult(
                content=f"Permission denied: {decision.reason}", is_error=True
            )
        if decision.action.value == "ask":
            if self.config.ask_async is not None:
                # Phase B.1: in-REPL modal path (loop-safe Future await).
                from eaccode.permissions.prompts import prompt_for_permission_async

                granted = await prompt_for_permission_async(
                    tc.name, tc.arguments,
                    session_rules=self.session_rules,
                    ask_async=lambda q: self.config.ask_async(tc.name, tc.arguments, q),  # type: ignore[misc]
                )
            else:
                granted = prompt_for_permission(
                    tc.name, tc.arguments, session_rules=self.session_rules
                )
            if not granted:
                from eaccode.tools.base import ToolResult

                return ToolResult(
                    content="User denied this action in the permission prompt",
                    is_error=True,
                )
        return await self.executor.execute(tc.name, tc.arguments, ctx.workdir, ctx=ctx)
