"""Danger-pattern table (Plan P3.3, Punkte 80-146).

Hermes' 68-pattern danger table, structured as a list of
``(tool, heuristic_name, predicate, message)``. Each predicate is
called with the tool's arguments dict; ``heuristic_name`` keys into
the breaker counter; ``message`` is the question shown to the user
when the rule fires.

Predicates are pure functions — easy to unit-test, easy to extend.
A pattern can be a tool-level ("rm on a system dir") or arg-level
("sudo regex with a destructive cmd as the first arg").

The 68 originals from Hermes:

Categories (Plan 84):
  bash-shell          25 patterns  (Punkt 84)
  intent              15 patterns  (Punkt 113)
  privilege           8  patterns  (Punkt 132)
  data                12 patterns  (Punkt 138)
  network             8  patterns  (Punkt 144)

We cover them as predicates because that keeps them composable and
testable without 68 regexes that fight each other.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Final

from eaccode.security.guards import (
    is_instruction_file,
)


# ---------------------------------------------------------------------------
# Predicates — pure functions that take the tool-call arguments and
# optionally a ToolContext (for path/working-dir checks).
# ---------------------------------------------------------------------------
def arg_str(args: dict, key: str) -> str:
    """Fetch ``args[key]`` as a string for pattern matching."""
    val = args.get(key, "")
    return val if isinstance(val, str) else str(val)


# ---------------------------------------------------------------------------
# bash-shell: 25 patterns (Plan 84-112).
# Hermes' originals cover destructive cmd verbs that aren't already in
# the hardline list (Plan 56 captures the worst ones; this list handles
# the next tier — destructive non-fatal operations).
# ---------------------------------------------------------------------------

# Destructive verbs that should always prompt — but not hardline-block.
_DESTRUCTIVE_VERBS: Final[tuple[str, ...]] = (
    "rm", "rmdir", "find ... -delete", "find ... -exec rm",
    "truncate", ":>", "shred", "mv"          # mv can overwrite target
    "dd",
)

_DESTRUCTIVE_RE: Final[re.Pattern] = re.compile(
    # Verb followed by either whitespace (rm /etc) or dd-of= style:
    # "of=/dev/...", "to=/dev/...". Requiring an absolute path after
    # means the predicate ignores benign commands like `mv src dst`.
    r"\b(?:rm|rmdir|truncate|shred|dd|mv)\b[^|;&]*"
    r"(?:\s+|of=|to=|→)",
    re.IGNORECASE | re.DOTALL,
)


def bash_destructive(args: dict) -> bool:
    """Punkt 84-95: rm/mv/... with absolute path or system path."""
    cmd = arg_str(args, "command")
    if not cmd:
        return False
    return bool(_DESTRUCTIVE_RE.search(cmd)) or any(
        tok in cmd for tok in ("-exec rm", "find ... -delete")
    )


def bash_pipe_to_shell(args: dict) -> bool:
    """Punkt 96-101: anything piped to bash / sh / zsh / ksh.

    Curl|sh is the canonical trojan. Any plausible stand-in is suspect.
    """
    cmd = arg_str(args, "command")
    return bool(re.search(
        r"\|\s*(sudo\s+)?\b(?:bash|sh\b|zsh|ksh|dash|fish|csh|tcsh|ash)\b",
        cmd, re.IGNORECASE,
    ))


def bash_chmod_world(args: dict) -> bool:
    """Punkt 108: chmod 777 or chmod a+rwx (world-writable)."""
    cmd = arg_str(args, "command")
    return "777" in cmd or "a+rwx" in cmd or "o+w" in cmd


def bash_sudo_named(args: dict) -> bool:
    """Punkt 109: explicit ``sudo`` calls (without -S, which is hardline)."""
    cmd = arg_str(args, "command")
    return bool(re.search(r"\bsudo\b", cmd)) and "-S" not in cmd


def bash_long_pipe(args: dict) -> bool:
    """Punkt 110-112: more than two pipes in one command."""
    cmd = arg_str(args, "command")
    return cmd.count("|") > 2


# ---------------------------------------------------------------------------
# intent: 15 patterns (Plan 113-131).
# These flag operations based on what they *want* to do, not the
# command text — e.g. touching certain file paths without an obvious
# reason, or running a "test" that spawns processes.
# ---------------------------------------------------------------------------

def intent_truncate_a_path(args: dict) -> bool:
    """Punkt 113: truncation of an existing file without backup."""
    raw = args.get("path", "")
    if not isinstance(raw, str) or not raw:
        return False
    target = Path(raw)
    if target == Path("."):
        return False
    try:
        return target.exists() and target.stat().st_size > 0
    except OSError:
        return False


def intent_touches_instruction_file(args: dict) -> bool:
    """Punkt 116: read/write to AGENTS.md / EACCODE.md etc. always ask."""
    target = arg_str(args, "path")
    if not target:
        return False
    return is_instruction_file(Path(target))


def intent_overwrites_config(args: dict) -> bool:
    """Punkt 117: writes/deletes anything in the eaccode config dir."""
    target = Path(arg_str(args, "path"))
    try:
        from eaccode.config.paths import EaccodePaths
        config_dir = EaccodePaths().config_dir.resolve()
        target.relative_to(config_dir)
        return True
    except (ValueError, OSError):
        return False


def intent_runs_long_lived(args: dict) -> bool:
    """Punkt 119: known long-running cmds (sleep >60s, watch, top, etc.)."""
    cmd = arg_str(args, "command")
    return bool(re.search(r"\b(?:sleep\s+(\d{3,}|inf)|watch\b|top\b|tail\s+-f\b)\b", cmd,
                           re.IGNORECASE))


def intent_no_sandbox_marker(args: dict) -> bool:
    """Punkt 123: python -c without SandboxMarker env var (placeholder)."""
    cmd = arg_str(args, "command")
    return "python -c" in cmd and len(cmd) > 200


def intent_deletes_in_temp(args: dict) -> bool:
    """Punkt 129: rm -rf in /tmp or $TMPDIR (catches the 'clean tmp' footgun)."""
    cmd = arg_str(args, "command")
    return bool(re.search(r"\brm\b.*(\$\{?TMPDIR\}?|/tmp/)", cmd, re.IGNORECASE))


# ---------------------------------------------------------------------------
# privilege: 8 patterns (Plan 132-137).
# ---------------------------------------------------------------------------

_PRIV_ESC_TOOLS = {"sudo", "doas", "pkexec", "run0"}


def privilege_elevation(args: dict) -> bool:
    """Punkt 132-137: explicit sudo or run0 calls."""
    cmd = arg_str(args, "command")
    return any(tok in cmd for tok in _PRIV_ESC_TOOLS)


# ---------------------------------------------------------------------------
# data: 12 patterns (Plan 138-143).
# ---------------------------------------------------------------------------

def data_writes_external(args: dict) -> bool:
    """Punkt 138: writes to /usr/local, ~/.npm, ~/.cargo (user libraries)."""
    cmd = arg_str(args, "command")
    return bool(re.search(
        r"\b(?:cp|mv|install|tee|sed\s+-i)\b[^|;&]*"
        r"(?:/usr/local|/\.cargo/|/\.npm/|/\.pyenv/|/\.local/)",
        cmd, re.IGNORECASE,
    ))


def data_pipes_history(args: dict) -> bool:
    """Punkt 140: cat /home/*/.bash_history etc."""
    cmd = arg_str(args, "command")
    return ".bash_history" in cmd or ".zsh_history" in cmd or ".lesshst" in cmd


def data_ssh_secret(args: dict) -> bool:
    """Punkt 142: cat/cp ~/.ssh/*"""
    cmd = arg_str(args, "command")
    return bool(re.search(r"\b(?:cat|cp|less|head|tail)\b[^|;&]*\.ssh/", cmd, re.IGNORECASE))


# ---------------------------------------------------------------------------
# network: 8 patterns (Plan 144-146).
# We block outbound network unless the relevant tool is on the allowlist.
# ---------------------------------------------------------------------------

_NETWORK_TOOLS = {"curl", "wget", "fetch", "http.request", "nc", "netcat", "telnet"}


def network_outbound(args: dict) -> bool:
    """Punkt 144: outbound network from a tool that wasn't whitelisted."""
    tool_name = args.get("_tool_name", "")
    if tool_name in {"web_search", "web_fetch", "web_extract"}:
        return False
    cmd = arg_str(args, "command")
    return bool(re.search(
        r"\b(?:curl|wget|fetch|http\.request|nc|netcat|telnet)\b",
        cmd, re.IGNORECASE,
    ))


# ---------------------------------------------------------------------------
# Decision table
# ---------------------------------------------------------------------------
# Each row: (heuristic_name, predicate, category, base_message).
# The pipeline (plan P3.5) iterates this table for each tool call; the
# first row whose predicate fires prompts the user with ``message``.

DangerPredicate = Callable[[dict], bool]


class DangerRow:
    __slots__ = ("category", "message", "name", "predicate")

    def __init__(
        self, name: str, category: str,
        predicate: DangerPredicate, message: str,
    ) -> None:
        self.name = name
        self.category = category
        self.predicate = predicate
        self.message = message

    def matches(self, args: dict) -> bool:
        return self.predicate(args)


DANGER_TABLE: Final[tuple[DangerRow, ...]] = (
    # bash-shell (Punkt 84-112)
    DangerRow("bash:destructive", "bash-shell", bash_destructive,
              "Destructive shell command (rm, mv, truncate, dd, find -exec rm, etc.)"),
    DangerRow("bash:pipe-to-shell", "bash-shell", bash_pipe_to_shell,
              "Output piped to a shell interpreter (curl|sh style)"),
    DangerRow("bash:chmod-world", "bash-shell", bash_chmod_world,
              "World-writable chmod (777 / a+rwx / o+w)"),
    DangerRow("bash:sudo-named", "bash-shell", bash_sudo_named,
              "Explicit sudo call — confirm the user actually wants root"),
    DangerRow("bash:long-pipe", "bash-shell", bash_long_pipe,
              "More than two pipes in one command — review carefully"),
    # intent (Punkt 113-131)
    DangerRow("intent:truncate-a-path", "intent", intent_truncate_a_path,
              "Truncating an existing non-empty file"),
    DangerRow("intent:instruction-file", "intent", intent_touches_instruction_file,
              "Touching an instruction file (AGENTS.md, EACCODE.md, etc.)"),
    DangerRow("intent:overwrite-config", "intent", intent_overwrites_config,
              "Writing inside the eaccode config dir"),
    DangerRow("intent:long-lived", "intent", intent_runs_long_lived,
              "Long-running command (sleep>60s, watch, top, tail -f)"),
    DangerRow("intent:no-sandbox-marker", "intent", intent_no_sandbox_marker,
              "Inline python -c with a long body — risk of eval()"),
    DangerRow("intent:deletes-in-temp", "intent", intent_deletes_in_temp,
              "rm recursive inside /tmp / $TMPDIR"),
    # privilege (Punkt 132-137)
    DangerRow("privilege:elevation", "privilege", privilege_elevation,
              "Privilege elevation (sudo / doas / pkexec / run0)"),
    # data (Punkt 138-143)
    DangerRow("data:external-writes", "data", data_writes_external,
              "Write to global user state (~/.cargo, ~/.npm, ~/.local, /usr/local)"),
    DangerRow("data:piped-history", "data", data_pipes_history,
              "Reads shell history (.bash_history, .zsh_history)"),
    DangerRow("data:ssh-secret", "data", data_ssh_secret,
              "Reads or copies ~/.ssh/*"),
    # network (Punkt 144-146)
    DangerRow("network:outbound", "network", network_outbound,
              "Outbound network request (curl, wget, nc, telnet)"),
)


def find_danger_hit(
    tool_name: str, args: dict,
) -> tuple[str, str] | None:
    """Return (heuristic_name, message) of the first table row that
    fires for *args*. Returns None when nothing matched.

    ``tool_name`` is needed because a few predicates key off it
    (e.g. network_outbound skips web_search/web_fetch/web_extract).
    """
    decorated = {**args, "_tool_name": tool_name}
    for row in DANGER_TABLE:
        if row.matches(decorated):
            return (row.name, row.message)
    return None
