"""Tests for the markdown renderer (v0.5.0, Hermes-style)."""

from eaccode.tui.markdown import render_markdown


def test_plain_text_passthrough():
    out = render_markdown("hello world")
    assert "hello world" in out


def test_code_block_muted():
    out = render_markdown("```py\nprint(1)\n```")
    assert "print(1)" in out


def test_inline_code():
    out = render_markdown("run `pytest` now")
    assert "pytest" in out
    assert "[" in out  # markup applied


def test_bold():
    out = render_markdown("**wichtig**")
    assert "wichtig" in out
    assert "bold" in out


def test_heading():
    out = render_markdown("# Titel")
    assert "Titel" in out
    assert "bold" in out


def test_list_bullets():
    out = render_markdown("- eins\n- zwei")
    assert "eins" in out
    assert "●" in out


def test_quote():
    out = render_markdown("> zitat")
    assert "zitat" in out
    assert "│" in out


def test_numbered_list():
    out = render_markdown("1. erster\n2. zweiter")
    assert "erster" in out
    assert "1." in out


def test_mixed_content():
    out = render_markdown("Text\n```\ncode\n```\nmehr")
    assert "Text" in out
    assert "code" in out
    assert "mehr" in out
