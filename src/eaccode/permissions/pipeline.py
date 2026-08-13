"""Permission-pipeline (Plan P3.5, Punkte 240-254).

Single entry point every tool call funnels through. Order of checks
(Plan 244-251):

  Step 0  preflight:  hardline / sudo-stdin / user-deny rules — Plan 56-79.
                       These do NOT prompt; they refuse outright.
  Step 1  system path: write/edit/delete against is_system_path() — Plan 224.
                       Also refused outright.
  Step 2  instruction file: write/edit against is_instruction_file() — Plan 229.
                          Always prompts, even under yolo.
  Step 3  allowlist:   ``eaccode permissions allow <pattern>``? Skip the prompt.
  Step 4  mode default: smart policy picks "auto" or "ask" based on tool category.
  Step 5  user config: ``approvals.mode=off/yolo`` overrides to never-ask.
  Step 6  danger table: 16-predicate danger check (Plan 80-146).
                         First matching predicate determines the prompt question.
  Step 7  ask user    : if no step above said skip/deny, fall through to prompt.

Hermes' exact order has more nuance around subcommands; we keep a
simpler, more conservative variant here. Each step may emit a tag
so the breaker counter (Plan 165-181) can attribute requests to
the step that produced them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from eaccode.permissions.allowlist import AllowlistStore as Allowlist
from eaccode.permissions.danger import find_danger_hit
from eaccode.permissions.hardline import (
    block_reason_text,
    preflight_block,
)
from eaccode.permissions.recognition import normalize_command
from eaccode.security.guards import is_instruction_file, is_system_path


class Mode(str, Enum):
    """Per-mode decisions for the prompt pipeline (Plan 240-247)."""
    DEFAULT = "default"           # smart policy
    AUTO = "auto"                 # never ask — execute all but hardline
    YOLO = "yolo"                 # skip every prompt (still hardline-block)
    OFF = "off"                   # same as YOLO (alias for clarity)
    ASK = "ask"                   # always ask, no smart policy


@dataclass
class Decision:
    """Result of running the pipeline once for a tool call."""
    action: str              # "allow" | "deny" | "ask"
    reason: str              # human-readable why
    block_kind: str | None = None    # "hardline" | "system_path" | "instruction_file" | "preflight"
    danger_name: str | None = None  # eaccode.permissions.danger row name


@dataclass
class PolicyContext:
    """State the pipeline reads from. Set once per session."""
    mode: Mode = Mode.DEFAULT
    yolo_armed: bool = False             # explicit /yolo or --yolo
    deny_patterns: tuple[str, ...] = field(default_factory=tuple)
    allowlist: Allowlist | None = None
    session_rules: tuple[str, ...] = field(default_factory=tuple)  # ephemeral session allow rules


def run_pipeline(
    tool_name: str,
    arguments: dict,
    *,
    ctx: PolicyContext,
) -> Decision:
    """The single pipeline. Returns a Decision — caller renders it.

    Arguments: same shape that ``AgentLoop`` hands to the permission
    gate (after coercion). ``tool_name`` is needed because a few
    checks key off the tool class, not just arguments.
    """
    # ---------- Step 1: system path / instruction file (writes/deletes) -----
    target = arguments.get("path") or arguments.get("target_path")
    if isinstance(target, str) and target:
        path = Path(target)
        # Always check instruction files first (Punkt 234) — they require
        # confirmation even under YOLO, so they're not just a Step 5 path.
        if is_instruction_file(path):
            return Decision(
                "ask",
                f"touching instruction file: {path.name}",
                block_kind="instruction_file",
            )
        if is_system_path(path):
            return Decision(
                "deny",
                f"system path: {target} — refused outright",
                block_kind="system_path",
            )

    # ---------- Step 0 (terminal case): bash destructive cmd with deny rule --
    # Hardline runs *only* for bash; the other steps handled file paths. If
    # a tool call is *only* a bash cmd without a path argument we get here
    # without the upstream checks. Run preflight now.
    if tool_name == "bash":
        cmd = str(arguments.get("command", ""))
        cmd = normalize_command(cmd)
        denied, kind, desc = preflight_block(cmd, deny_patterns=ctx.deny_patterns)
        if denied:
            return Decision("deny", block_reason_text(kind, desc),
                            block_kind=kind or "preflight")

    # ---------- Step 2 + 3: allowlist + mode ----------
    if ctx.allowlist and ctx.allowlist.check(tool_name, arguments):
        return Decision("allow", "matched allowlist")

    # Mode-based decisions: in yolo/off the only thing we still block
    # is the preflight and the system path; everything else is allowed.
    if ctx.mode in (Mode.YOLO, Mode.OFF) or ctx.yolo_armed:
        return Decision("allow", "mode=yolo")

    # ---------- Step 4 + 5: danger table → prompt question ----------
    hit = find_danger_hit(tool_name, arguments)
    if hit:
        danger_name, danger_msg = hit
        return Decision(
            "ask",
            f"{danger_name}: {danger_msg}",
            block_kind="danger",
            danger_name=danger_name,
        )

    # ---------- Step 6: default is "ask" if unknown ----------
    return Decision("ask", "policy: ask (default)")


def _session_rule_key(tool_name: str, arguments: dict) -> str:
    """A short identifier for the tool call, used as allowlist key.

    For ``bash`` we hash the command (same input -> same key).
    For everything else we hash the tool name + path/argument.
    """
    import hashlib

    if tool_name == "bash":
        cmd = normalize_command(str(arguments.get("command", "")))
        return "bash:" + hashlib.sha256(cmd.encode()).hexdigest()[:16]
    if "path" in arguments:
        return f"{tool_name}:{arguments['path']}"
    return f"{tool_name}:general"


__all__ = [
    "Decision",
    "Mode",
    "PolicyContext",
    "run_pipeline",
]
