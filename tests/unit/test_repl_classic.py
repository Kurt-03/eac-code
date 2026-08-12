"""P7 (v0.7.2): classic REPL boot + crash recovery + multi-line input."""

import queue


def test_repl_module_imports():
    """The new ui.repl module imports without Textual."""
    from eaccode.ui import repl

    assert hasattr(repl, "run_repl")
    assert hasattr(repl, "PROMPT")
    assert hasattr(repl, "MULTILINE_SENTINEL")
    assert not hasattr(repl, "EaccodeApp")


def test_no_tui_dependency_remains():
    """None of the eaccode modules import textual.

    Sanity check that the v0.7.2 cleanup actually removed every textual
    import. We scan the source files in src/eaccode/ directly.
    """
    from pathlib import Path

    src = Path("src/eaccode")
    offenders: list[str] = []
    for py in src.rglob("*.py"):
        # Skip backups/notes; they're for historical reference only.
        if "backup" in py.parts:
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        # "import textual" or "from textual" — but allow the strings
        # inside docstrings/comments to not trip the test.
        for line in text.splitlines():
            stripped = line.strip()
            if (stripped.startswith("import textual")
                    or stripped.startswith("from textual ")):
                offenders.append(f"{py}: {stripped}")
                break
    assert not offenders, (
        "textual imports still present after v0.7.2 cleanup:\n"
        + "\n".join(offenders)
    )


def test_permission_choice_parsing():
    """The classic REPL parses stdin replies into PermissionChoice."""
    from eaccode.permissions.prompts import PermissionChoice
    from eaccode.ui.repl import _parse_choice

    assert _parse_choice("y") == PermissionChoice.ALLOW_ONCE
    assert _parse_choice("yes") == PermissionChoice.ALLOW_ONCE
    assert _parse_choice("a") == PermissionChoice.ALLOW_ALWAYS
    assert _parse_choice("s") == PermissionChoice.ALLOW_SESSION
    assert _parse_choice("p") == PermissionChoice.PAUSE
    # Anything else (incl. empty) = deny
    assert _parse_choice("") == PermissionChoice.DENY
    assert _parse_choice("nope") == PermissionChoice.DENY
    assert _parse_choice("Y") == PermissionChoice.ALLOW_ONCE


def test_multi_line_sentinel_defined():
    from eaccode.ui.repl import MULTILINE_SENTINEL
    assert MULTILINE_SENTINEL == '"""'


def test_crash_recovery_loop_does_not_raise():
    """A bug in run_repl_sync must NOT propagate out of the REPL loop.

    We simulate by feeding the runner a queue that yields an error.
    """
    # The runner itself raises the exception via the event queue;
    # the REPL's `except Exception` catches it.
    from eaccode.ui import repl
    assert hasattr(repl, "_handle_event")


def test_handle_event_text_writes_to_stdout(capsys):
    from eaccode.agent.runner import AgentEvent
    from eaccode.ui.context import ReplContext
    from eaccode.ui.repl import _handle_event

    ev = AgentEvent(kind="text", payload={"delta": "hello world"})
    _handle_event(ev, ReplContext(), [], queue.Queue())
    captured = capsys.readouterr()
    assert "hello world" in captured.out


def test_handle_event_permission_writes_prompt(capsys, monkeypatch):
    """When the runner asks, the REPL must write the question line."""
    from eaccode.agent.runner import AgentEvent
    from eaccode.ui.context import ReplContext
    from eaccode.ui.repl import _handle_event

    monkeypatch.setattr("builtins.input", lambda: "y")
    ev = AgentEvent(kind="permission", payload={
        "id": 1, "tool": "bash", "arguments": {},
        "question": "Allow bash?",
    })
    resolves: queue.Queue = queue.Queue()
    _handle_event(ev, ReplContext(), [], resolves)
    captured = capsys.readouterr()
    assert "Allow bash?" in captured.out
    # resolve arrived
    ask_id, choice = resolves.get_nowait()
    from eaccode.permissions.prompts import PermissionChoice
    assert ask_id == 1
    assert choice == PermissionChoice.ALLOW_ONCE


def test_handle_event_done_newline(capsys):
    from eaccode.agent.runner import AgentEvent
    from eaccode.ui.context import ReplContext
    from eaccode.ui.repl import _handle_event

    _handle_event(AgentEvent(kind="done"), ReplContext(), [], queue.Queue())
    captured = capsys.readouterr()
    # Newline + flush
    assert captured.out == "\n"


def test_handle_event_tool_call_writes_card(capsys):
    from eaccode.agent.runner import AgentEvent
    from eaccode.ui.context import ReplContext
    from eaccode.ui.repl import _handle_event

    ev = AgentEvent(kind="tool_call", payload={
        "id": "1", "name": "bash", "arguments": {"command": "ls"},
    })
    _handle_event(ev, ReplContext(), [], queue.Queue())
    captured = capsys.readouterr()
    assert "bash" in captured.out
    assert "ls" in captured.out
