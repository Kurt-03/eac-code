"""Tool-call guardrails (Phase C.2) — loop detection + runaway caps.

Ported from Hermes' ``agent/tool_guardrails.py`` (MIT, Aug 2026). Pure
controller: tracks per-turn tool-call observations and returns decisions
(allow | warn | block | halt). Runtime code owns whether decisions become
warning guidance, synthetic tool results, or controlled turn halts.

Three signal classes, mirroring Hermes:
- exact-failure loop — the SAME call (tool + canonical args) failed N times.
- same-tool failure loop — a tool failed N times this turn, regardless of
  args. Warns with a strategy hint instead of the same retry.
- idempotent no-progress — a read-style tool returned the SAME result N
  times; repeating it unchanged is wasting tokens.
- runaway caps — hard per-turn ceilings for web_search and delegate_task
  (counters reset every turn).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from eaccode.tools.base import ToolClass


@dataclass(frozen=True)
class GuardrailConfig:
    """Thresholds for per-turn tool-call loop detection."""

    warnings_enabled: bool = True
    hard_stop_enabled: bool = False  # warnings never block execution by default
    exact_failure_warn_after: int = 2
    exact_failure_block_after: int = 5
    same_tool_failure_warn_after: int = 3
    same_tool_failure_halt_after: int = 8
    no_progress_warn_after: int = 2
    no_progress_block_after: int = 5
    max_web_searches: int = 50
    max_subagents: int = 50


@dataclass(frozen=True)
class ToolCallSignature:
    """Stable identity for a tool name plus canonical args (no raw values)."""

    tool_name: str
    args_hash: str

    @classmethod
    def from_call(cls, tool_name: str, args: Mapping[str, Any] | None) -> ToolCallSignature:
        canonical = json.dumps(
            args or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        )
        return cls(
            tool_name=tool_name,
            args_hash=hashlib.sha256(canonical.encode()).hexdigest()[:16],
        )


@dataclass(frozen=True)
class GuardrailDecision:
    """Decision returned by the guardrail controller."""

    action: str = "allow"  # allow | warn | block | halt
    code: str = "allow"
    message: str = ""
    tool_name: str = ""
    count: int = 0
    signature: ToolCallSignature | None = None

    @property
    def allows_execution(self) -> bool:
        return self.action in ("allow", "warn")

    @property
    def should_halt(self) -> bool:
        return self.action in ("block", "halt")


def _tool_failure_recovery_hint(tool_name: str, count: int) -> str:
    """Strategy hint when a tool keeps failing (Hermes parity)."""
    hints = {
        "bash": "The command failed repeatedly. Quote paths with spaces, "
                "avoid shell metacharacters in arguments, or break it into "
                "smaller steps.",
        "write": "The file write failed repeatedly. Check the path is "
                 "writable and outside eaccode's protected directories.",
        "edit": "The edit failed repeatedly. Read the file first — the "
                "old_string may have drifted.",
        "web_search": "The search failed repeatedly. Try a different query "
                      "or use web_fetch on a known URL instead.",
        "web_fetch": "The fetch failed repeatedly. Try web_search for the "
                     "content, or check the URL scheme.",
        "execute_code": "The script failed repeatedly. Add print() "
                        "statements to debug, or split the logic.",
        "delegate_task": "The delegation failed repeatedly. Reduce the "
                         "goal's scope or inline the work.",
    }
    hint = hints.get(tool_name, "Inspect the error and change strategy "
                              "instead of retrying it unchanged.")
    return f"{tool_name} failed {count}x this turn. {hint}"


class ToolCallGuardrailController:
    """Per-turn controller for repeated failed/non-progressing tool calls."""

    def __init__(self, config: GuardrailConfig | None = None) -> None:
        self.config = config or GuardrailConfig()
        self.reset_for_turn()

    def reset_for_turn(self) -> None:
        self._exact_failure_counts: dict[ToolCallSignature, int] = {}
        self._same_tool_failure_counts: dict[str, int] = {}
        self._no_progress: dict[ToolCallSignature, tuple[str, int]] = {}
        self._halt_decision: GuardrailDecision | None = None
        self._turn_web_search_count = 0
        self._turn_subagent_count = 0

    @property
    def halt_decision(self) -> GuardrailDecision | None:
        return self._halt_decision

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _coerce_args(args: Mapping[str, Any] | None) -> dict:
        return dict(args or {})

    def _is_idempotent(self, tool_name: str, registry=None) -> bool:
        if registry is not None:
            try:
                return registry.get(tool_name).tool_class == ToolClass.IDEMPOTENT
            except KeyError:
                pass
        return tool_name in {"read", "glob", "grep", "web_fetch", "session_search",
                             "clarify", "todo_write"}

    # ------------------------------------------------------------ decisions

    def before_call(self, tool_name: str, args: Mapping[str, Any] | None,
                    registry=None) -> GuardrailDecision:
        """Called before a tool executes. May block (runaway caps)."""
        signature = ToolCallSignature.from_call(tool_name, self._coerce_args(args))

        # Per-turn runaway caps (hard ceilings, independent of hard_stop).
        if tool_name == "web_search":
            if (self.config.max_web_searches
                    and self._turn_web_search_count >= self.config.max_web_searches):
                decision = GuardrailDecision(
                    action="block", code="loop_web_search_cap",
                    message=(f"Blocked web_search: this turn has already made "
                             f"{self.config.max_web_searches} searches. This looks "
                             "like a runaway search loop — work with the results "
                             "you already have."),
                    tool_name=tool_name, count=self._turn_web_search_count,
                    signature=signature,
                )
                self._halt_decision = decision
                return decision
            self._turn_web_search_count += 1
        elif tool_name == "delegate_task":
            if self.config.max_subagents and self._turn_subagent_count >= self.config.max_subagents:
                decision = GuardrailDecision(
                    action="block", code="loop_subagent_cap",
                    message=(f"Blocked delegate_task: this turn has already spawned "
                             f"{self.config.max_subagents} subagents. Finish the work "
                             "with the results you have."),
                    tool_name=tool_name, count=self._turn_subagent_count,
                    signature=signature,
                )
                self._halt_decision = decision
                return decision
            self._turn_subagent_count += 1

        if not self.config.hard_stop_enabled:
            return GuardrailDecision(tool_name=tool_name, signature=signature)

        # Hard-stop mode: block repeated exact failures / no-progress.
        exact_count = self._exact_failure_counts.get(signature, 0)
        if exact_count >= self.config.exact_failure_block_after:
            decision = GuardrailDecision(
                action="block", code="repeated_exact_failure_block",
                message=(f"Blocked {tool_name}: the same call failed {exact_count} "
                         "times with identical arguments. Change strategy."),
                tool_name=tool_name, count=exact_count, signature=signature,
            )
            self._halt_decision = decision
            return decision

        if self._is_idempotent(tool_name, registry):
            record = self._no_progress.get(signature)
            if record is not None and record[1] >= self.config.no_progress_block_after:
                decision = GuardrailDecision(
                    action="block", code="idempotent_no_progress_block",
                    message=(f"Blocked {tool_name}: this read-only call returned "
                             f"the same result {record[1]} times. Use the result "
                             "already provided or try a different query."),
                    tool_name=tool_name, count=record[1], signature=signature,
                )
                self._halt_decision = decision
                return decision

        return GuardrailDecision(tool_name=tool_name, signature=signature)

    def after_call(self, tool_name: str, args: Mapping[str, Any] | None,
                   result: str | None, *, failed: bool | None = None,
                   registry=None) -> GuardrailDecision:
        """Called after a tool executes. May warn (never blocks)."""
        args = self._coerce_args(args)
        signature = ToolCallSignature.from_call(tool_name, args)
        if failed is None:
            failed = bool(
                result and (result.startswith("Error") or "error" in result[:200].lower())
            )

        if failed:
            exact_count = self._exact_failure_counts.get(signature, 0) + 1
            self._exact_failure_counts[signature] = exact_count
            self._no_progress.pop(signature, None)

            same_count = self._same_tool_failure_counts.get(tool_name, 0) + 1
            self._same_tool_failure_counts[tool_name] = same_count

            if (self.config.hard_stop_enabled
                    and same_count >= self.config.same_tool_failure_halt_after):
                decision = GuardrailDecision(
                    action="halt", code="same_tool_failure_halt",
                    message=(f"Stopped {tool_name}: it failed {same_count} times "
                             "this turn. Choose a different approach."),
                    tool_name=tool_name, count=same_count, signature=signature,
                )
                self._halt_decision = decision
                return decision

            if self.config.warnings_enabled and exact_count >= self.config.exact_failure_warn_after:
                return GuardrailDecision(
                    action="warn", code="repeated_exact_failure_warning",
                    message=(f"{tool_name} failed {exact_count}x with identical "
                             "arguments. This looks like a loop — change strategy."),
                    tool_name=tool_name, count=exact_count, signature=signature,
                )
            if (self.config.warnings_enabled
                    and same_count >= self.config.same_tool_failure_warn_after):
                return GuardrailDecision(
                    action="warn", code="same_tool_failure_warning",
                    message=_tool_failure_recovery_hint(tool_name, same_count),
                    tool_name=tool_name, count=same_count, signature=signature,
                )
            return GuardrailDecision(tool_name=tool_name, count=exact_count, signature=signature)

        # Success: clear failure counters.
        self._exact_failure_counts.pop(signature, None)
        self._same_tool_failure_counts.pop(tool_name, None)

        if not self._is_idempotent(tool_name, registry):
            self._no_progress.pop(signature, None)
            return GuardrailDecision(tool_name=tool_name, signature=signature)

        result_hash = hashlib.sha256((result or "").encode()).hexdigest()[:16]
        previous = self._no_progress.get(signature)
        repeat_count = 1
        if previous is not None and previous[0] == result_hash:
            repeat_count = previous[1] + 1
        self._no_progress[signature] = (result_hash, repeat_count)

        if self.config.warnings_enabled and repeat_count >= self.config.no_progress_warn_after:
            return GuardrailDecision(
                action="warn", code="idempotent_no_progress_warning",
                message=(f"{tool_name} returned the same result {repeat_count} "
                         "times. Use the result already provided or change the query."),
                tool_name=tool_name, count=repeat_count, signature=signature,
            )
        return GuardrailDecision(tool_name=tool_name, count=repeat_count, signature=signature)
