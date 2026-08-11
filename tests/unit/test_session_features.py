"""Tests for session export + recap + leases (D.3/D.5/D.8)."""


from eaccode.llm.models import Message
from eaccode.sessions.export import export_html, export_markdown, write_export
from eaccode.sessions.leases import (
    acquire_lease,
    active_leases,
    cleanup_stale_leases,
    release_lease,
)
from eaccode.sessions.recap import recap
from eaccode.sessions.store import Session


def _session() -> Session:
    return Session(
        id="sess-12345678",
        title="Fix build",
        messages=[
            Message.user("hello there"),
            Message.assistant("hi"),
            Message.tool_result("t1", "output"),
        ],
        metadata={"cwd": "/tmp"},
        created_at="2026-08-11T10:00:00",
        updated_at="2026-08-11T10:05:00",
    )


def test_export_markdown_contains_conversation():
    md = export_markdown(_session())
    assert "# Fix build" in md
    assert "hello there" in md
    assert "hi" in md


def test_export_html_escapes():
    session = _session()
    session.messages[0] = Message.user("<script>alert(1)</script>")
    html = export_html(session)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_write_export_creates_file(tmp_path):
    dest = write_export(_session(), "md", tmp_path)
    assert dest.exists()
    assert dest.suffix == ".md"
    html_dest = write_export(_session(), "html", tmp_path)
    assert html_dest.suffix == ".html"


def test_recap_tail_only():
    text = recap(_session(), count=2)
    assert "hello there" in text
    assert "Fix build" in text


def test_recap_no_messages():
    s = _session()
    s.messages = []
    assert "(no conversational messages)" in recap(s)


# ---------------------------------------------------------------- D.8


def test_lease_lifecycle(tmp_path):
    lock = acquire_lease(tmp_path, "abc")
    assert lock.exists()
    assert active_leases(tmp_path) == ["abc"]
    release_lease(lock)
    assert active_leases(tmp_path) == []


def test_cleanup_removes_dead_pid(tmp_path):
    import json
    import os

    lock = tmp_path / "dead.lock"
    lock.write_text(json.dumps({"pid": 99999999, "session": "dead"}),
                    encoding="utf-8")
    assert cleanup_stale_leases(tmp_path) == 1
    assert not lock.exists()
    # A live pid (ours) survives.
    live = tmp_path / "live.lock"
    live.write_text(json.dumps({"pid": os.getpid(), "session": "live"}),
                    encoding="utf-8")
    assert cleanup_stale_leases(tmp_path) == 0
    assert live.exists()


def test_corrupt_lock_is_removed(tmp_path):
    (tmp_path / "bad.lock").write_text("{broken", encoding="utf-8")
    assert cleanup_stale_leases(tmp_path) == 1
    assert active_leases(tmp_path) == []
