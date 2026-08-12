"""P7 (v0.7.2): dispatch_slash adapts the existing _cmd_* machinery."""

from eaccode.ui.context import ReplContext
from eaccode.ui.dispatch import dispatch_slash


def test_dispatch_help_returns_command_list():
    ctx = ReplContext()
    out, should_exit = dispatch_slash("/help", ctx)
    assert "/help" in out
    assert should_exit is False


def test_dispatch_exit_sets_should_exit():
    ctx = ReplContext()
    out, should_exit = dispatch_slash("/exit", ctx)
    assert should_exit is True


def test_dispatch_unknown_command():
    ctx = ReplContext()
    out, should_exit = dispatch_slash("/nonsense_xyz", ctx)
    assert "Unknown command" in out or "not wired" in out
    assert should_exit is False


def test_dispatch_strips_markup():
    """Rich markup tags must not leak into the classic REPL output."""
    ctx = ReplContext()
    out, _ = dispatch_slash("/help", ctx)
    # Help text historically contained [bold] etc. — strip them.
    import re
    assert not re.search(r"\[/?[a-z]+/?\]", out), out


def test_dispatch_handles_systemexit():
    """Even if a command calls sys.exit, the REPL catches it."""
    ctx = ReplContext()
    out, should_exit = dispatch_slash("/exit", ctx)
    assert should_exit is True


def test_dispatch_mode_reports_usage_without_arg():
    ctx = ReplContext()
    out, _ = dispatch_slash("/mode", ctx)
    assert "Usage" in out or "Valid" in out or "default" in out
