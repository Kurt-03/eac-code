"""Tool-result classification — did the mutation actually land? (Phase H.5)

Ported from Hermes' ``agent/tool_result_classification.py``. An
``is_error=False`` result that doesn't prove the mutation landed lets
the LLM loop on "did it work?"; the guardrails use this to detect
repeated non-progress on mutating tools.
"""

from __future__ import annotations

import re
from pathlib import Path

_WROTE_RE = re.compile(r"wrote \d+ bytes to (.+?)(?:$|\n)", re.IGNORECASE)
_EDITED_RE = re.compile(r"edited (.+?)(?:$|\n)", re.IGNORECASE)


def file_mutation_result_landed(tool_name: str, result: str | None,
                                cwd: str | None = None) -> bool:
    """True when the tool result actually proves the file mutation landed.

    For write: the result says "Wrote N bytes to <path>" AND the file
    exists (when resolvable). For edit: result says "Edited <path>" AND
    the file exists.
    """
    if not result:
        return False

    if tool_name in ("write", "edit"):
        match = _WROTE_RE.search(result) or _EDITED_RE.search(result)
        if match is None:
            return False
        path_str = match.group(1).strip()
        try:
            path = Path(path_str)
            if not path.is_absolute() and cwd:
                path = Path(cwd) / path
            return path.exists()
        except OSError:
            return False

    # Other tools: treat a successful (non-error) result as landed.
    return not result.startswith("Error")
