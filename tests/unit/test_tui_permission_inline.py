"""Tests for the v0.4.0 inline permission prompt (TUI redesign Phase B)."""



def test_inline_prompt_header():
    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt("read", {"path": "a.py"})
    assert "Allow read?" in text
    assert "path: a.py" in text


def test_inline_prompt_keys_line():
    """v0.5.3: the [y]/[a]/[n]/[p] legend must SURVIVE Rich markup —
    the transcript Log runs with markup=True, which previously parsed
    the keys as style tags and silently ate them."""
    from rich.markup import render

    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt("write", {"path": "x.py",
                                              "content": "hello"})
    # Raw string carries the escapes…
    assert "\\[y] once" in text
    # …and the rendered text shows every key.
    plain = render(text).plain
    assert "[y] once" in plain
    assert "[a] always" in plain
    assert "[n] deny" in plain
    assert "[p] pause" in plain
    assert "[Esc] deny" in plain


def test_markup_in_diff_is_preserved():
    """v0.5.3: code like ``[x for x in y]`` in a diff must not be eaten
    by the Rich markup parser."""
    from rich.markup import render

    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt(
        "write", {"path": "a.py"},
        diff="+print([x for x in y])",
    )
    plain = render(text).plain
    assert "+print([x for x in y])" in plain


def test_markup_in_args_is_preserved():
    from rich.markup import render

    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt(
        "write", {"path": "a.py", "content": "x = [red, green]"},
    )
    plain = render(text).plain
    assert "x = [red, green]" in plain


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


# ---------------------------------------------------------------------------
# v0.0.1: ALLOW_SESSION quick-pick + visible legend
# ---------------------------------------------------------------------------


def test_inline_prompt_lists_all_keys_with_descriptions():
    """v0.0.1: the legend shows y/s/a/n/p with descriptive labels."""
    from rich.markup import render

    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt("bash", {"command": "ls"})
    plain = render(text).plain
    # All five keys and their descriptions must appear in the rendered text.
    for key in ("[y]", "[s]", "[a]", "[n]", "[p]"):
        assert key in plain, f"missing key {key} in prompt: {plain!r}"
    for label in ("once", "session", "always", "deny", "pause"):
        assert label in plain, f"missing label {label!r} in prompt: {plain!r}"
