"""Session export (D.3) — markdown and HTML from stored messages."""

from __future__ import annotations

import html as html_mod
from datetime import datetime
from pathlib import Path

from eaccode.sessions.store import Session


def export_markdown(session: Session) -> str:
    """Full conversation as markdown (title + messages)."""
    lines = [
        f"# {session.title}",
        f"\n> session `{session.id}` · {session.created_at}",
        "",
    ]
    for m in session.messages:
        role = m.role.value.upper()
        text = m.text or ""
        if m.tool_calls:
            names = ", ".join(tc.name for tc in m.tool_calls)
            text = f"{text}\n\n*tools: {names}*" if text else f"*tools: {names}*"
        lines.append(f"## {role}\n\n{text}\n")
    return "\n".join(lines)


def export_html(session: Session) -> str:
    """Conversation as a standalone HTML page."""
    body: list[str] = []
    for m in session.messages:
        role = m.role.value
        text = html_mod.escape(m.text or "")
        body.append(
            f'<div class="msg {role}"><strong>{role}</strong>'
            f"<pre>{text}</pre></div>"
        )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{html_mod.escape(session.title)}</title>"
        "<style>body{font-family:sans-serif;max-width:800px;margin:2em auto}"
        ".msg{margin:1em 0;padding:.6em;border-left:3px solid #888}"
        ".user{border-color:#2a6}.assistant{border-color:#26a}"
        "pre{white-space:pre-wrap}</style></head><body>"
        f"<h1>{html_mod.escape(session.title)}</h1>"
        + "".join(body)
        + "</body></html>"
    )


def write_export(session: Session, fmt: str, out_dir: Path) -> Path:
    """Write the export file; returns its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ext = "html" if fmt == "html" else "md"
    dest = out_dir / f"session-{session.id[:8]}-{stamp}.{ext}"
    content = export_html(session) if fmt == "html" else export_markdown(session)
    dest.write_text(content, encoding="utf-8")
    return dest
