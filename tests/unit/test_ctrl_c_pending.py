"""P7/A.5: Ctrl+C during a pending permission prompt denies + cancels."""



async def test_ctrl_c_during_pending_denies_and_cancels(tmp_path):
    from textual.widgets import Input

    from eaccode.ui.repl import EaccodeApp
    from tests.unit.test_repl_permission_flow import (
        _make_agent,
        _prepare_app,
        _wait_for,
    )

    app = EaccodeApp(workdir=tmp_path)
    agent, _client = _make_agent(tmp_path, app._ask_permission_async)
    await _prepare_app(tmp_path, agent, app)

    async with app.run_test() as pilot:
        inp = app.query_one("#input", Input)
        inp.value = "schreibe out.txt"
        await pilot.press("enter")
        assert await _wait_for(
            app,
            lambda: getattr(app, "_pending_permission", None) is not None,
        ), "permission prompt never became pending"

        # Ctrl+C while pending — should deny and clear pending.
        app.action_quit_or_cancel()
        await pilot.pause(0.05)
        assert getattr(app, "_pending_permission", None) is None, (
            "pending must clear after Ctrl+C"
        )
        assert not (tmp_path / "out.txt").exists(), "deny means no write"

        # Wait for the cancelled turn to complete (busy False).
        assert await _wait_for(app, lambda: not app._busy, tries=200), (
            "turn must finish after Ctrl+C cancel"
        )
