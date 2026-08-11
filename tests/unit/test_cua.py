"""Tests for the cua-driver client + computer_use tools (Phase I.5)."""

import pytest

from eaccode.tools import cua
from eaccode.tools.base import ToolContext


class FakeDriver:
    """Replaces cua._run_driver: records the command, returns canned JSON."""

    def __init__(self, reply: dict):
        self.reply = reply
        self.commands: list[dict] = []

    def run(self, command: dict, timeout: float = 60.0) -> dict:
        self.commands.append(command)
        return self.reply


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path)


@pytest.fixture
def fake_driver(monkeypatch):
    fake = FakeDriver({"ok": True, "elements": [{"n": 1, "role": "button"}]})
    monkeypatch.setattr("eaccode.tools.cua._run_driver", fake.run)
    monkeypatch.setattr("eaccode.tools.cua.driver_available", lambda: True)
    return fake


def test_cua_capture_parses_som(fake_driver):
    out = cua.cua_capture(mode="som", app="Safari")
    assert out["elements"][0]["n"] == 1
    assert fake_driver.commands[0]["action"] == "capture"
    assert fake_driver.commands[0]["params"]["app"] == "Safari"


def test_cua_browser_navigate_uses_tab_capability(fake_driver):
    out = cua.cua_browser_navigate(url="https://example.com", tab_id="t1")
    assert out["elements"][0]["n"] == 1
    cmd = fake_driver.commands[0]
    assert cmd["action"] == "cua_browser_navigate"
    assert cmd["params"]["url"] == "https://example.com"
    assert cmd["params"]["tab_id"] == "t1"


def test_driver_missing_raises_setup_hint(monkeypatch):
    monkeypatch.setattr("eaccode.tools.cua.find_driver", lambda: None)
    with pytest.raises(FileNotFoundError, match="computer install"):
        cua.cua_capture()


def test_driver_error_reply_raises(monkeypatch, tmp_path):
    """The real _run_driver must surface ok:false replies as RuntimeError."""
    binary = tmp_path / "cua-driver"
    binary.write_text("fake", encoding="utf-8")
    monkeypatch.setattr("eaccode.tools.cua.find_driver", lambda: binary)

    class _Proc:
        returncode = 0
        stdout = '{"ok": false, "error": "accessibility api unavailable"}'
        stderr = ""

    monkeypatch.setattr(
        "eaccode.tools.cua.subprocess.run",
        lambda *a, **k: _Proc(),
    )
    with pytest.raises(RuntimeError, match="accessibility api"):
        cua.cua_capture()


def test_non_json_driver_output_raises(monkeypatch, tmp_path):
    binary = tmp_path / "cua-driver"
    binary.write_text("fake", encoding="utf-8")
    monkeypatch.setattr("eaccode.tools.cua.find_driver", lambda: binary)

    class _Proc:
        returncode = 0
        stdout = "not json at all"
        stderr = ""

    monkeypatch.setattr(
        "eaccode.tools.cua.subprocess.run",
        lambda *a, **k: _Proc(),
    )
    with pytest.raises(RuntimeError, match="non-JSON"):
        cua.cua_capture()


def test_read_only_action_set():
    assert "capture" in cua.READ_ONLY_ACTIONS
    assert "click" not in cua.READ_ONLY_ACTIONS


class TestCaptureTool:
    @pytest.mark.asyncio
    async def test_capture_free_and_parses(self, ctx, fake_driver):
        from eaccode.tools.builtin.computer_use import (
            CaptureInput,
            ComputerUseCaptureTool,
        )

        tool = ComputerUseCaptureTool()
        assert tool.requires_permission is False
        result = await tool.run(CaptureInput(mode="som", app="Safari"), ctx)
        assert result.is_error is False
        assert "button" in result.content

    @pytest.mark.asyncio
    async def test_invalid_mode_rejected(self, ctx, fake_driver):
        from eaccode.tools.builtin.computer_use import (
            CaptureInput,
            ComputerUseCaptureTool,
        )

        result = await ComputerUseCaptureTool().run(
            CaptureInput(mode="hologram"), ctx
        )
        assert result.is_error is True
        assert fake_driver.commands == []  # nothing dispatched

    @pytest.mark.asyncio
    async def test_no_driver_graceful(self, ctx, monkeypatch):
        from eaccode.tools.builtin.computer_use import (
            CaptureInput,
            ComputerUseCaptureTool,
        )

        monkeypatch.setattr("eaccode.tools.cua.driver_available", lambda: False)
        result = await ComputerUseCaptureTool().run(CaptureInput(), ctx)
        assert result.is_error is True
        assert "computer install" in result.content


class TestComputerUseTool:
    @pytest.mark.asyncio
    async def test_click_dispatches(self, ctx, fake_driver):
        from eaccode.tools.builtin.computer_use import (
            ComputerUseInput,
            ComputerUseTool,
        )

        tool = ComputerUseTool()
        assert tool.requires_permission is True
        result = await tool.run(
            ComputerUseInput(action="click", element=3, button="right"), ctx
        )
        assert result.is_error is False
        cmd = fake_driver.commands[0]
        assert cmd["action"] == "click"
        assert cmd["params"]["element"] == 3
        assert cmd["params"]["button"] == "right"

    @pytest.mark.asyncio
    async def test_type_requires_text(self, ctx, fake_driver):
        from eaccode.tools.builtin.computer_use import (
            ComputerUseInput,
            ComputerUseTool,
        )

        result = await ComputerUseTool().run(ComputerUseInput(action="type"), ctx)
        assert result.is_error is True
        assert "requires text" in result.content

    @pytest.mark.asyncio
    async def test_browser_navigate(self, ctx, fake_driver):
        from eaccode.tools.builtin.computer_use import (
            ComputerUseInput,
            ComputerUseTool,
        )

        result = await ComputerUseTool().run(
            ComputerUseInput(action="cua_browser_navigate",
                             url="https://example.com"),
            ctx,
        )
        assert result.is_error is False
        assert fake_driver.commands[0]["action"] == "cua_browser_navigate"

    @pytest.mark.asyncio
    async def test_unknown_action(self, ctx, fake_driver):
        from eaccode.tools.builtin.computer_use import (
            ComputerUseInput,
            ComputerUseTool,
        )

        result = await ComputerUseTool().run(
            ComputerUseInput(action="self_destruct"), ctx
        )
        assert result.is_error is True
        assert "Unknown" in result.content

    @pytest.mark.asyncio
    async def test_no_driver_graceful(self, ctx, monkeypatch):
        """Same setup hint as the capture tool — no driver, no dispatch."""
        from eaccode.tools.builtin.computer_use import (
            ComputerUseInput,
            ComputerUseTool,
        )

        monkeypatch.setattr("eaccode.tools.cua.driver_available", lambda: False)
        result = await ComputerUseTool().run(
            ComputerUseInput(action="click", element=1), ctx
        )
        assert result.is_error is True
        assert "computer install" in result.content


class TestRegistry:
    def test_tools_registered(self):
        from eaccode.tools.factory import build_default_registry

        reg = build_default_registry()
        names = {t.name for t in reg.list()}
        assert {"computer_use", "computer_use_capture"} <= names

    def test_computer_use_toolset_gating(self):
        from eaccode.tools.factory import build_default_registry

        reg = build_default_registry(enabled_toolsets=["file"])
        names = {t.name for t in reg.list()}
        assert "computer_use" not in names
        assert "read" in names
