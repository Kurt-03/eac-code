"""Tests for the v0.4.0 flat layout (TUI redesign Phase A.1).

The ``TUILayout`` is a tiny dataclass describing what the App renders:
log + separator + input + status bar. We test it without mounting a
real Textual App (faster, deterministic).
"""



def test_layout_default_no_boxes():
    from eaccode.tui.layout import TUILayout

    layout = TUILayout()
    assert layout.has_header is False
    assert layout.has_footer is False
    assert layout.has_input_border is False
    assert layout.has_log_border is False


def test_layout_status_bar_position():
    from eaccode.tui.layout import TUILayout

    layout = TUILayout()
    # Status bar at the bottom (after log + separator + input).
    assert layout.regions[-1] == "status_bar"
    assert "log" in layout.regions
    assert "input" in layout.regions
    assert "separator" in layout.regions


def test_layout_separator_is_horizontal_line():
    from eaccode.tui.layout import TUILayout

    layout = TUILayout()
    sep = layout.separator(width=10)
    assert sep == "─" * 10


def test_layout_color_palette_minimal():
    """Only one accent + dim — no primary/success/error/warning bunting."""
    from eaccode.tui.layout import TUILayout

    layout = TUILayout()
    palette = layout.palette
    assert palette.accent in {"cyan", "yellow", "magenta"}
    assert palette.dim
    assert palette.muted
    # Should NOT include success/error/warning colour slots.
    assert not hasattr(palette, "success")
    assert not hasattr(palette, "warning")
    assert not hasattr(palette, "error")
