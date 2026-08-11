"""Tests for the v0.4.0 flat-message renderer (TUI redesign Phase A.3)."""



def test_render_user_marker():
    from eaccode.tui.render import render_message

    assert render_message("user", "hallo") == "› hallo"


def test_render_assistant_plain():
    from eaccode.tui.render import render_message

    assert render_message("assistant", "Done.") == "Done."


def test_render_tool_call_header():
    from eaccode.tui.render import render_message

    line = render_message("tool_call", "", name="read",
                          args={"path": "a.py"})
    assert line.startswith("▸ read ")
    assert "a.py" in line


def test_render_tool_call_with_command():
    from eaccode.tui.render import render_message

    line = render_message("tool_call", "", name="bash",
                          args={"command": "ls"})
    assert "▸ bash" in line
    assert "ls" in line


def test_render_tool_result_indented():
    from eaccode.tui.render import render_message

    line = render_message("tool_result", "hello\nworld")
    assert line.startswith("    ")  # 4-space indent
    assert "hello" in line


def test_render_reasoning_marker():
    from eaccode.tui.render import render_message

    line = render_message("reasoning", "thinking...")
    assert "[reasoning]" in line
    assert "thinking..." in line


def test_render_error_marker():
    from eaccode.tui.render import render_message

    line = render_message("error", "boom")
    assert "✗" in line
    assert "boom" in line


def test_render_unknown_role_passes_through():
    from eaccode.tui.render import render_message

    assert render_message("system", "boot") == "boot"


def test_args_summary_truncates_long_values():
    from eaccode.tui.render import _args_summary

    s = _args_summary({"path": "x" * 200})
    assert len(s) < 200
    assert "…" in s or len(s) <= 80
