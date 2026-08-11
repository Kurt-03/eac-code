"""safeAuto classification (B.2) — auto-approve safe bash, ASK on risky.

Two layers:
1. **Key patterns** (fast, deterministic): clearly destructive or
   exfiltrating commands are risky without any LLM round-trip.
2. **Aux-LLM classifier** (llm.aux_classifier): anything else is asked;
   the verdict is cached per command string. When the aux model is
   unavailable the result is *not* safe — the policy falls back to the
   manual path (ASK), never to silent auto-allow.
"""

from __future__ import annotations

import re

# Pattern -> reason. Order matters: first match wins.
_RM_FLAGS = re.compile(r"-\w*r\w*|--recursive")
_RM_FORCE = re.compile(r"-\w*f\w*|--force")


def _rm_risky(command: str) -> str | None:
    """rm is risky when it combines a recursive flag with a force flag."""
    if not re.search(r"\brm\s+-", command):
        return None
    tail = command.split("rm", 1)[1]
    return "recursive forced delete" if (_RM_FLAGS.search(tail)
                                        and _RM_FORCE.search(tail)) else None


RISKY_PATTERNS: list[tuple[object, str]] = [
    (_rm_risky, "recursive forced delete"),
    (re.compile(r"\bcurl[^|&;]*\|\s*(ba)?sh\b", re.I), "curl-pipe-to-shell"),
    (re.compile(r"\bwget[^|&;]*\|\s*(ba)?sh\b", re.I), "wget-pipe-to-shell"),
    (re.compile(r"\bbase64\s+-d\b", re.I), "base64 decode (obfuscation)"),
    (re.compile(r"\bmkfs|fdisk\b", re.I), "disk formatting"),
    (re.compile(r"\bdd\s+if=.*of=/dev/", re.I), "raw block device write"),
    (re.compile(r"\bchmod\s+(-R\s+)?777\b", re.I), "world-writable permissions"),
    (re.compile(r"\bsudo\s+rm\b", re.I), "privileged delete"),
    (re.compile(r"\bgit\s+push\s+.*--force", re.I), "forced push"),
    (re.compile(r"\b>+\s*/etc/|>>\s*/etc/", re.I), "system config write"),
    (re.compile(r"\bssh\s+[^@]+@", re.I), "remote shell"),
    (re.compile(r"\bscp\b", re.I), "remote file copy"),
    (re.compile(r"\bnc\s+-", re.I), "netcat"),
    (re.compile(r"\bpython\s+-c\s*['\"]import\s+os", re.I), "python os escape"),
    (re.compile(r":\(\)\s*\{", re.I), "fork bomb"),
]

_cache: dict[str, str] = {}  # command -> verdict (per-process)


def key_pattern_risk(command: str) -> str | None:
    """Return the risk reason when a key pattern matches, else None."""
    for matcher, reason in RISKY_PATTERNS:
        if callable(matcher):
            if matcher(command):
                return reason
        elif matcher.search(command):
            return reason
    return None


def is_command_safe(command: str, *, use_llm: bool = True) -> bool:
    """True → auto-approve; False → ASK (or risky).

    Never returns True on classifier failure — unknown means ask.
    """
    if not command.strip():
        return True
    if key_pattern_risk(command):
        return False
    cached = _cache.get(command)
    if cached is not None:
        return cached == "safe"
    if not use_llm:
        return False
    from eaccode.llm.aux_classifier import classify_command

    verdict = classify_command(command)
    if verdict is None:
        return False  # fail open to manual — never auto-allow on doubt
    _cache[command] = verdict
    return verdict == "safe"


def clear_cache() -> None:
    _cache.clear()
