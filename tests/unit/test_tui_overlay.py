"""Tests for the v0.4.0 SuggestionOverlay (TUI redesign Phase C.1)."""



def test_overlay_starts_empty():
    from eaccode.tui.overlay import SuggestionOverlay

    ov = SuggestionOverlay()
    assert ov.current() is None
    assert ov.items == []


def test_overlay_set_items_and_current():
    from eaccode.tui.overlay import SuggestionOverlay

    ov = SuggestionOverlay()
    ov.set_items([("/help", "Show commands"), ("/history", "View history")])
    assert ov.current() == ("/help", "Show commands")


def test_overlay_move_delta():
    from eaccode.tui.overlay import SuggestionOverlay

    ov = SuggestionOverlay()
    ov.set_items([("/a", "a"), ("/b", "b"), ("/c", "c")])
    ov.move(1)
    assert ov.current() == ("/b", "b")
    ov.move(1)
    assert ov.current() == ("/c", "c")
    ov.move(1)
    assert ov.current() == ("/c", "c")  # clamp at end


def test_overlay_move_negative():
    from eaccode.tui.overlay import SuggestionOverlay

    ov = SuggestionOverlay()
    ov.set_items([("/a", "a"), ("/b", "b")])
    ov.move(-1)
    assert ov.current() == ("/a", "a")  # clamp at start


def test_overlay_render_lines():
    from eaccode.tui.overlay import SuggestionOverlay

    ov = SuggestionOverlay()
    ov.set_items([("/help", "Show commands"), ("/history", "View history")])
    lines = ov.render_lines()
    assert "▸ /help" in lines[0]
    assert "  /history" in "\n".join(lines)


def test_overlay_render_caps_at_eight():
    from eaccode.tui.overlay import SuggestionOverlay

    ov = SuggestionOverlay(max_visible=8)
    ov.set_items([(f"/cmd{i}", f"d{i}") for i in range(20)])
    lines = ov.render_lines()
    # 8 visible + 1 "(+N more)" trailing line.
    assert len(lines) == 9
    assert lines[-1].startswith("  …")
