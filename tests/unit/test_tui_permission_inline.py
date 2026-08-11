"""Tests for the v0.4.0 inline permission prompt (TUI redesign Phase B)."""



def test_inline_prompt_header():
    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt("read", {"path": "a.py"})
    assert "Allow read?" in text
    assert "path: a.py" in text


def test_inline_prompt_keys_line():
    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt("write", {"path": "x.py",
                                              "content": "hello"})
    assert "[y] once" in text
    assert "[a] always" in text
    assert "[n] deny" in text
    assert "[p] pause" in text
    assert "[Esc] deny" in text


def test_inline_prompt_includes_diff_when_provided():
    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt("edit", {"path": "x.py"},
                                   diff="--- a/x\n+++ b/x\n-old\n+new")
    assert "--- a/x" in text
    assert "+new" in text


def test_inline_prompt_no_diff_means_no_diff_lines():
    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt("read", {"path": "a.py"})
    assert "---" not in text


def test_inline_prompt_truncates_long_values():
    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt("write", {"path": "a.py",
                                              "content": "x" * 500})
    # Long values get truncated.
    assert "x" * 200 not in text
    assert "…" in text
