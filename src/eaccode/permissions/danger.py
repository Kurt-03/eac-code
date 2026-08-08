"""Danger heuristics for smart approval mode (Phase A.5).

Deterministic, zero-cost classification: destructive or credential-
touching shell commands are flagged for confirmation; everything else is
auto-approved in smart mode (mirroring Claude Code's /permission behavior
and Hermes' smart approvals without the auxiliary LLM).
"""
from __future__ import annotations

import re

DANGER_PATTERNS = [
    re.compile(r"\brm\s+(-[a-z]*r[a-z]*\s+)?(-[a-z]*f[a-z]*\s+)?", re.I),
    re.compile(r"\brm\s+-rf\b", re.I),
    re.compile(r"\brmdir\s+/s\b", re.I),
    re.compile(r"\bdel\s+/[sqf]", re.I),
    re.compile(r"\bgit\s+reset\s+--hard\b", re.I),
    re.compile(r"\bgit\s+clean\s+-[a-z]*f", re.I),
    re.compile(r"\bgit\s+push\s+(-f|--force)\b", re.I),
    re.compile(r"\bgit\s+checkout\s+--\s", re.I),
    re.compile(r"\bformat\s+[a-z]:", re.I),
    re.compile(r"\bshutdown\b|\breboot\b|\bhalt\b", re.I),
    re.compile(r"\bdd\s+if=", re.I),
    re.compile(r"\bmkfs\b|\bdiskpart\b", re.I),
    re.compile(r"\bchmod\s+[0-7]{3}\s+/", re.I),
    re.compile(r"\bchown\s+", re.I),
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"\bpip\s+uninstall\b", re.I),
    re.compile(r"\bcurl\b.*\|\s*(ba)?sh\b", re.I),
    re.compile(r"\bwget\b.*\|\s*(ba)?sh\b", re.I),
    re.compile(r">+\s*[\"']?[^|;&<>]*\.(env|pem|key|p12)\b", re.I),
    re.compile(r"\b[\w./~-]+\.(pem|key|p12)\b", re.I),
    re.compile(r"\breg\s+delete\b", re.I),
    re.compile(r"\btaskkill\s+/f\b", re.I),
]


def is_dangerous(command: str) -> bool:
    """True if the shell command looks destructive or credential-touching."""
    return any(p.search(command) for p in DANGER_PATTERNS)
