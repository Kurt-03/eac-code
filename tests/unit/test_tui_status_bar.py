"""Tests for the v0.4.0 status bar (TUI redesign Phase A.4)."""



def test_status_bar_renders_compact():
    from eaccode.tui.status_bar import StatusBar

    bar = StatusBar(model="MiniMax-M3", mode="safeAuto",
                    context_pct=42, cost_usd=0.0123)
    text = bar.render()
    # Compact, single-line, with all four anchors.
    assert "MiniMax-M3" in text
    assert "safeAuto" in text
    assert "42%" in text
    assert "0.01" in text  # rounded cost


def test_status_bar_handles_unknown_values():
    from eaccode.tui.status_bar import StatusBar

    bar = StatusBar(model="", mode="", context_pct=None, cost_usd=0.0)
    text = bar.render()
    assert "—" in text  # placeholder for missing model/mode


def test_status_bar_no_cost_when_zero_optional():
    from eaccode.tui.status_bar import StatusBar

    bar = StatusBar(model="x", mode="default", context_pct=0, cost_usd=0.0)
    text = bar.render()
    # Don't print "$0.0000" clutter.
    assert "$0" not in text
