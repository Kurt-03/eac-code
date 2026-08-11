"""v0.4.0 list-style suggester (TUI redesign Phase C.2).

Unlike the old single-suggestion API (``get_suggestion`` returning one
string), this module returns a *list* of ``(name, description)`` pairs
— the SuggestionOverlay renders them as a filtered menu below the
input, sorted by length then alphabetically (Hermes-style).
"""

from __future__ import annotations

from eaccode.ui.command_def import COMMAND_REGISTRY

_AT_REFS = (
    ("@diff", "Git working tree diff"),
    ("@staged", "Git staged diff"),
    ("@file:", "Attach a file"),
    ("@folder:", "Attach a folder"),
    ("@git:", "Git log with diffs (e.g. @git:5)"),
    ("@url:", "Fetch web content"),
)


def list_slash_completions(text: str) -> list[tuple[str, str]]:
    """Return all matching ``(name, description)`` pairs for ``/cmd``.

    Empty string returns the full registry; anything starting with ``/``
    filters by the prefix (without the leading slash). Sorted by length
    (kürzere zuerst) then alphabetically — Hermes convention so /h /he
    /hel always lights up the shortest match.
    """
    if not text:
        # The user hasn't typed anything yet — return the full list.
        out = [(cmd.name, cmd.description) for cmd in COMMAND_REGISTRY]
        out.sort(key=lambda pair: (len(pair[0]), pair[0]))
        return out
    if not text.startswith("/"):
        return []
    prefix = text[1:].lower()
    out: list[tuple[str, str]] = []
    for cmd in COMMAND_REGISTRY:
        for candidate in (cmd.name, *cmd.aliases):
            if candidate.startswith(prefix):
                out.append((candidate, cmd.description))
                break
    out.sort(key=lambda pair: (len(pair[0]), pair[0]))
    return out


def list_at_completions(text: str) -> list[tuple[str, str]]:
    """Return all matching ``(label, description)`` pairs for ``@ref``."""
    if not text.startswith("@"):
        return []
    prefix = text.lower()
    out = [(label, desc) for label, desc in _AT_REFS
           if label.lower().startswith(prefix)]
    out.sort(key=lambda pair: (len(pair[0]), pair[0]))
    return out
