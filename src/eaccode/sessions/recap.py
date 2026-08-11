"""Session recap (D.5) — compact summary of a session's tail."""

from __future__ import annotations

from eaccode.sessions.store import Session

RECAP_MESSAGES = 6


def recap(session: Session, count: int = RECAP_MESSAGES) -> str:
    """Last *count* user/assistant messages, one line each."""
    lines = [f"# {session.title}", ""]
    shown = 0
    for m in reversed(session.messages):
        if m.role.value not in ("user", "assistant") or not m.text:
            continue
        text = " ".join(m.text.split())[:100]
        lines.insert(1, f"- **{m.role.value}**: {text}")
        shown += 1
        if shown >= count:
            break
    if shown == 0:
        lines.append("(no conversational messages)")
    return "\n".join(lines)
