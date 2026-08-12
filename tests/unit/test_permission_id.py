"""P7/B.4: permission prompt carries the approval id; /approve <id> resolves."""

from rich.markup import render


def test_prompt_carries_approval_id():
    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt(
        "write", {"path": "a.py"}, approval_id=42,
    )
    plain = render(text).plain
    assert "#42" in plain
    assert "Allow write?" in plain


def test_prompt_works_without_id():
    from eaccode.tui.render import render_permission_prompt

    text = render_permission_prompt("read", {"path": "a.py"})
    plain = render(text).plain
    assert "#" not in plain
    assert "Allow read?" in plain
