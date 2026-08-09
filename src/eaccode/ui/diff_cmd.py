"""/diff — git diff for the current session (staged|all|session).

Uses ``bounded_git_probe`` (Phase A.4) so a private remote can never
hang the REPL on a credential prompt, and renders the diff through the
same code as the permission-modal preview (Phase B.2).
"""

from __future__ import annotations

from eaccode._subprocess_compat import bounded_git_probe


def run_diff(mode: str, app) -> str:
    """Return the git diff for the requested mode as a string.

    Modes:
      staged (default) — ``git diff --staged``
      all              — ``git diff HEAD``
      session          — diff of files the agent touched this session
    """
    if mode == "session":
        touched = getattr(app, "_session_touched", None)
        if not touched:
            return "No files were touched in this session yet."
        paths = list(touched)
        if len(paths) > 12:
            paths = paths[:12]
        diff = bounded_git_probe(["git", "diff", "HEAD", "--", *paths], timeout=30)
        if not diff:
            return "No uncommitted changes in session-touched files."
        return diff

    if mode == "all":
        diff = bounded_git_probe(["git", "diff", "HEAD"], timeout=30)
    else:  # staged
        diff = bounded_git_probe(["git", "diff", "--staged"], timeout=30)
    if not diff:
        return "No diff." if mode == "staged" else "No diff against HEAD."
    return diff
