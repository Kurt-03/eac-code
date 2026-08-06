"""Prompt-injection scanner (Task 6.2) — blocks the pattern, not the file."""
from __future__ import annotations

import re

_PATTERNS = [
    re.compile(
        r"ignore (?:all |any |previous |prior )*(?:instructions|prompts|rules)", re.I
    ),
    re.compile(
        r"disregard (?:previous |prior |all )*.{0,40}(?:instructions|prompts)", re.I
    ),
    re.compile(r"(you are now|act as if).{0,60}(without|regardless)", re.I),
    re.compile(r"delete (?:all |the )?(?:everything|files|data|repo|entire)", re.I),
    re.compile(r"exfiltrat|steal (?:api|keys|secrets|credentials)", re.I),
]


def scan_for_injection(text: str) -> str:
    for pat in _PATTERNS:
        text = pat.sub("[BLOCKED: potential prompt injection]", text)
    return text
