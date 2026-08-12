"""P7/E.2: first-run branding banner."""

from rich.markup import render


def test_banner_text_present():
    """The banner must mention the version (so support tickets are easier)."""
    from eaccode.ui.repl import EaccodeApp

    app = EaccodeApp(workdir=None)
    text = "\n".join(app._render_onboarding())
    plain = render(text).plain
    assert "eaccode" in plain
    assert "v0." in plain or "v1." in plain
    assert "Plan7" in plain or "autonomous" in plain
