"""Tests for the fuzzy slash overlay (v0.5.0)."""

from eaccode.tui.slash_overlay import SlashOverlay


def test_update_filters_commands():
    overlay = SlashOverlay()
    overlay.update("/mo")
    names = [item["name"] for item in overlay.items]
    assert "mode" in names
    assert "model" in names


def test_empty_without_slash():
    overlay = SlashOverlay()
    overlay.update("hello")
    assert overlay.items == []


def test_current_none_when_empty():
    overlay = SlashOverlay()
    assert overlay.current() is None


def test_move_clamps():
    overlay = SlashOverlay()
    overlay.update("/")
    count = len(overlay.items)
    overlay.move(count + 10)
    assert overlay.current() is not None
    overlay.move(-100)
    assert overlay.current() is not None


def test_render_lines_marker():
    overlay = SlashOverlay()
    overlay.update("/")
    lines = overlay.render_lines()
    assert lines
    assert "▸ /" in lines[0]


def test_render_caps_visible():
    overlay = SlashOverlay(max_visible=4)
    overlay.update("/")
    assert len(overlay.visible()) <= 4


def test_rank_by_description():
    overlay = SlashOverlay()
    overlay.update("/permission")
    names = [item["name"] for item in overlay.items]
    assert "mode" in names  # description contains "permission mode"
