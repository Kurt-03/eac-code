"""Tests for the Hermes-style status rule (v0.5.0)."""

from eaccode.tui.status_rule import StatusRule


def test_render_idle():
    rule = StatusRule(model="MiniMax-M3", right_label="C:\\proj")
    text = rule.render()
    assert "MiniMax-M3" in text
    assert "idle" in text
    assert "C:\\proj" in text


def test_render_busy_with_indicator():
    rule = StatusRule(busy=True, indicator="⠋", verb="working…",
                      model="m", right_label="x")
    text = rule.render()
    assert "⠋" in text
    assert "working…" in text


def test_render_context():
    rule = StatusRule(model="m", context_used=12_000, context_max=200_000)
    text = rule.render()
    assert "12k/200k tok" in text
    assert "█" in text  # context bar


def test_context_bar_fraction():
    rule = StatusRule(model="m", context_used=100_000, context_max=200_000)
    assert "50%" in rule.render()


def test_render_drops_right_label_on_narrow():
    rule = StatusRule(model="MiniMax-M3", right_label="very-long-label")
    wide = rule.render(cols=200)
    narrow = rule.render(cols=20)
    assert "very-long-label" in wide
    assert "very-long-label" not in narrow


def test_render_cost_when_positive():
    rule = StatusRule(model="m", cost_usd=0.0123)
    assert "$0.0123" in rule.render()


def test_render_no_cost_when_zero():
    rule = StatusRule(model="m", cost_usd=0.0)
    assert "$" not in rule.render()
