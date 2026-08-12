"""v0.0.1: pin that the REPL does NOT push the legacy PermissionModal.

The old `PermissionModal` (a ModalScreen) was kept around for tests but
never used in the REPL path. The REPL renders an inline permission
question in the transcript and decides via the PermissionAwareInput
key interception. Pushing a ModalScreen would steal focus from the
composer and break the inline UX.

This test asserts that `_ask_permission_async` does NOT push a screen.
"""
from __future__ import annotations

from typing import Any

import pytest


class _FakeLog:
    """Minimal stand-in for textual RichLog."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, text: str) -> None:
        self.lines.append(text)


class _FakeStatic:
    def __init__(self) -> None:
        self.content = ""

    def update(self, text: str) -> None:
        self.content = text


class _FakeInput:
    disabled = False

    def focus(self) -> None:
        pass


@pytest.mark.asyncio
async def test_repl_permission_does_not_push_modal() -> None:
    """The REPL's _ask_permission_async must NOT call push_screen."""
    from eaccode.tui.app import EaccodeApp

    log = _FakeLog()
    static = _FakeStatic()
    input_ = _FakeInput()
    pushed: list[Any] = []

    class _StubApp:
        workdir = type("P", (), {"__str__": lambda self: "/tmp"})()
        _pending_permission = None
        _approvals = type(
            "A",
            (),
            {
                "register": lambda self, *a, **kw: 1,
                "pending": lambda self: [],
            },
        )()

        def query_one(self, selector: str, cls: Any = None) -> Any:
            if selector == "#transcript":
                return log
            if selector == "#input":
                return input_
            return static

        def push_screen(self, screen: Any) -> None:
            pushed.append(screen)

        def _diff_preview(self, tool: str, args: dict) -> str | None:
            return None  # no diff preview for this test

        def _restore_input_after_permission(self, fut: Any) -> None:
            pass  # no-op for the stub

        def _on_approval_resolved(self, tool: str, args: dict, fut: Any) -> None:
            pass  # no-op for the stub

    stub = _StubApp()
    future = EaccodeApp._ask_permission_async(
        stub, "bash", {"command": "ls"}, "run command?"
    )
    assert len(log.lines) > 0, "permission prompt not written to transcript"
    assert pushed == [], f"push_screen was called: {pushed}"
    # The future is pending; resolve it to clean up.
    future.set_result("allow-once")


def test_repl_permission_renders_in_transcript() -> None:
    """The inline prompt must render in the transcript (no separate UI)."""
    from eaccode.tui.render import render_permission_prompt

    expected = render_permission_prompt("bash", {"command": "ls"})
    # The expected header must contain y/s/a/n/p legend (v0.0.1).
    assert "[y]" in expected
    assert "[s]" in expected
    assert "[a]" in expected
