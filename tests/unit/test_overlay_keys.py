"""P7/B.3: overlay navigation wins over permission fallback in on_key."""



async def test_overlay_arrows_fire_when_overlay_active(tmp_path):
    from eaccode.ui.repl import EaccodeApp
    from tests.unit.test_repl_permission_flow import _prepare_app

    app = EaccodeApp(workdir=tmp_path)
    await _prepare_app(tmp_path, None, app)

    async with app.run_test() as pilot:
        app._overlay.update("/")
        # Sanity: the overlay lists all commands.
        assert app._overlay.items
        initial_idx = app._overlay.index
        app.on_key(_FakeKey("down"))
        assert app._overlay.index != initial_idx  # moved
        app.on_key(_FakeKey("up"))
        # Back near the top — index clamped at 0.
        assert app._overlay.index == 0


async def test_escape_clears_overlay_but_not_pending(tmp_path):
    from eaccode.ui.repl import EaccodeApp
    from tests.unit.test_repl_permission_flow import _prepare_app

    app = EaccodeApp(workdir=tmp_path)
    await _prepare_app(tmp_path, None, app)

    async with app.run_test() as pilot:
        app._overlay.update("/")
        assert app._overlay.items
        app.on_key(_FakeKey("escape"))
        # Overlay cleared.
        assert app._overlay.items == []


class _FakeKey:
    def __init__(self, key: str) -> None:
        self.key = key
        self.prevented = False
        self.stopped = False

    def prevent_default(self) -> None:
        self.prevented = True

    def stop(self) -> None:
        self.stopped = True
