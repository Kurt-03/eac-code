"""Error classification (F.32) — transient | permanent | needs_input.

Drives retry policy: transient errors (rate limits, timeouts, 5xx) get
retried, permanent errors (auth, schema) fail fast, needs_input errors
(permission, missing file) surface to the user immediately.
"""

from __future__ import annotations

import re
from typing import Any

_TRANSIENT = re.compile(
    r"rate.?limit|too many requests|timeout|timed out|temporarily|"
    r"overloaded|429|5\d\d|connection (reset|refused)|server error",
    re.I,
)
_PERMANENT = re.compile(
    r"unauthorized|authentication|api[ _-]?key|invalid (api|request)|"
    r"permission denied|not found|404|400|schema|validation error",
    re.I,
)
_NEEDS_INPUT = re.compile(
    r"permission|approval|confirm|missing (argument|parameter)|"
    r"required field|interactive",
    re.I,
)


def classify_error(error: Any) -> str:
    """'transient' | 'permanent' | 'needs_input' for an exception."""
    text = f"{type(error).__name__}: {error}"
    if _PERMANENT.search(text) and not _TRANSIENT.search(text):
        return "permanent"
    if _NEEDS_INPUT.search(text):
        return "needs_input"
    if _TRANSIENT.search(text):
        return "transient"
    return "transient"  # unknown errors get one retry, then surface


def should_retry(error: Any, attempts: int, max_attempts: int = 2) -> bool:
    """True when the error is transient and retries remain."""
    return classify_error(error) == "transient" and attempts < max_attempts
