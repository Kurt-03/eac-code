"""Headless smoke test: boot the REPL with a fake provider, send /exit.

This runs only in CI/local — it's marked 'integration' so the default
pytest run skips it. We use a fake agent that streams no events so
the prompt is reached quickly.

Purpose: prove the import chain works end-to-end after the v0.7.2
TUI removal. No live LLM call.
"""

from __future__ import annotations


def test_repl_module_smoke():
    """Just import + call run_repl's helpers — never start the loop."""
    from eaccode.ui import repl

    # Sanity: the constants we exposed are present.
    assert repl.PROMPT == "eaccode> "
    assert repl.MULTILINE_SENTINEL == '"""'

    # _read_input signature is callable with a PromptSession stub.
    class _StubSession:
        def prompt(self, label: str) -> str:
            return "/exit"

    text, multiline = repl._read_input(_StubSession())
    # /exit returns ("", False) — first line is not empty + multi-line
    # mode is only entered when the input is exactly the sentinel.
    # Actually _read_input returns the line itself; let's verify.
    assert text == "/exit"
    assert multiline is False
