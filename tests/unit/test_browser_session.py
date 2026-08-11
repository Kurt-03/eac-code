"""Tests for the CDP browser session (Phase I.7) — mocked WebSocket."""

import json
import time

import pytest

from eaccode.tools.browser.actions import (
    console_output,
    dialog_state,
    get_images,
    handle_dialog,
)
from eaccode.tools.browser.session import (
    CdpBrowser,
    CdpSession,
    _parse_modifiers,
    find_browser,
)


class FakeWS:
    """WebSocket double: answers each sent command from a response table.

    ``recv`` blocks until a reply is queued (like a real socket), so the
    session's background reader thread stays alive between commands.
    """

    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.sent: list[dict] = []
        self._queue: list[str] = []
        self.closed = False

    def send(self, payload: str) -> None:
        msg = json.loads(payload)
        self.sent.append(msg)
        result = self.responses.get(msg["method"])
        if result is None:
            reply = {"id": msg["id"],
                     "error": {"message": f"no fake response for {msg['method']}"}}
        else:
            reply = {"id": msg["id"], "result": result}
        self._queue.append(json.dumps(reply))

    def recv(self) -> str:
        deadline = time.monotonic() + 5
        while not self._queue:
            if self.closed or time.monotonic() > deadline:
                raise ConnectionError("fake ws closed")
            time.sleep(0.005)
        return self._queue.pop(0)

    def settimeout(self, _t: float) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def _make_browser(responses: dict[str, dict]) -> tuple[CdpBrowser, FakeWS]:
    import urllib.request

    ws = FakeWS(responses)
    payload = json.dumps(
        [{"type": "page", "webSocketDebuggerUrl": "ws://fake"}]
    ).encode()

    class _FakeResp:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(urllib.request, "urlopen",
                   lambda _url, **kwargs: _FakeResp())
        browser = CdpBrowser.connect(port=9333, ws_factory=lambda _u: ws)
    return browser, ws


def test_find_browser_returns_path_or_none():
    # No assertion on the exact binary (platform-dependent) — must not crash
    # and must return a Path when one is installed.
    result = find_browser()
    assert result is None or result.exists()


def test_parse_modifiers():
    assert _parse_modifiers("ctrl+s") == ("s", 2)
    assert _parse_modifiers("ctrl+shift+enter") == ("Enter", 10)
    assert _parse_modifiers("plain") is None
    assert _parse_modifiers("ctrl+") is None


class TestSession:
    def test_send_returns_result_and_tracks_console(self):
        import urllib.request

        ws = FakeWS({
            "Runtime.evaluate": {"result": {"value": "hello"}},
        })
        session = CdpSession(port=9333, ws_factory=lambda _u: ws)

        class _FakeResp:
            def read(self):
                return json.dumps(
                    [{"type": "page", "webSocketDebuggerUrl": "ws://fake"}]
                ).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        # Inject the target list by faking the /json endpoint fetch.
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(urllib.request, "urlopen",
                       lambda _url, **kwargs: _FakeResp())
            try:
                session.connect()
                result = session.send("Runtime.evaluate", {"expression": "1"})
                assert result["result"]["value"] == "hello"
                assert ws.sent[0]["method"] == "Runtime.evaluate"
            finally:
                session.close()


class TestBrowser:
    def test_navigate_waits_for_ready_state(self):
        browser, ws = _make_browser({
            "Page.navigate": {},
            "Runtime.evaluate": {"result": {"value": "complete"}},
        })
        out = browser.navigate("https://example.com")
        assert out == {"url": "https://example.com", "status": "loaded"}
        assert ws.sent[0]["params"]["url"] == "https://example.com"

    def test_snapshot_builds_refs(self):
        browser, _ws = _make_browser({
            "Accessibility.getFullAXTree": {"nodes": [
                {"role": {"value": "button"}, "name": {"value": "Save"},
                 "backendDOMNodeId": 41},
                {"role": {"value": "heading"}, "name": {"value": "Title"},
                 "backendDOMNodeId": 42},
                {"role": {"value": "none"}, "name": {"value": ""},
                 "backendDOMNodeId": 43},
            ]},
        })
        text = browser.snapshot()
        assert "[@e1] button: Save" in text
        assert "[@e2] heading: Title" in text
        assert "e3" not in text  # empty/none nodes are skipped
        assert len(browser._elements) == 2

    def test_click_uses_element_center(self):
        browser, ws = _make_browser({
            "Accessibility.getFullAXTree": {"nodes": [
                {"role": {"value": "button"}, "name": {"value": "Go"},
                 "backendDOMNodeId": 7},
            ]},
            "DOM.getBoxModel": {"model": {"content": [10, 20, 30, 20,
                                                       30, 40, 10, 40]}},
            "Input.dispatchMouseEvent": {},
        })
        browser.snapshot()
        out = browser.click("@e1")
        assert out["clicked"] == "@e1"
        events = [m for m in ws.sent if m["method"] == "Input.dispatchMouseEvent"]
        assert len(events) == 2  # pressed + released
        assert events[0]["params"]["x"] == 20.0  # center of the quad
        assert events[0]["params"]["y"] == 30.0

    def test_click_unknown_ref_raises(self):
        browser, _ws = _make_browser({"Accessibility.getFullAXTree": {"nodes": []}})
        browser.snapshot()
        with pytest.raises(ValueError):
            browser.click("@e99")

    def test_scroll_directions(self):
        browser, ws = _make_browser({"Input.dispatchMouseEvent": {}})
        browser.scroll("down", amount=3)
        browser.scroll("up", amount=1)
        wheels = [m["params"] for m in ws.sent
                  if m["method"] == "Input.dispatchMouseEvent"]
        assert wheels[0]["deltaY"] == 300
        assert wheels[1]["deltaY"] == -100
        with pytest.raises(ValueError):
            browser.scroll("sideways")

    def test_back_uses_history(self):
        browser, ws = _make_browser({
            "Page.getNavigationHistory": {
                "currentIndex": 2,
                "entries": [{"id": 1, "url": "a"}, {"id": 2, "url": "b"},
                            {"id": 3, "url": "c"}],
            },
            "Page.navigateToHistoryEntry": {},
        })
        out = browser.back()
        assert out == {"back": True, "to": "b"}
        assert ws.sent[-1]["params"]["entryId"] == 2

    def test_back_no_history(self):
        browser, _ws = _make_browser({
            "Page.getNavigationHistory": {"currentIndex": 0, "entries": []},
        })
        assert browser.back()["back"] is False

    def test_evaluate_returns_value(self):
        browser, _ws = _make_browser({
            "Runtime.evaluate": {"result": {"value": 42}},
        })
        assert browser.evaluate("40+2") == 42

    def test_type_and_press(self):
        browser, ws = _make_browser({"Input.insertText": {},
                                     "Input.dispatchKeyEvent": {}})
        browser.type("hello")
        browser.press("enter")
        methods = [m["method"] for m in ws.sent]
        assert "Input.insertText" in methods
        keys = [m["params"]["key"] for m in ws.sent
                if m["method"] == "Input.dispatchKeyEvent"]
        assert keys == ["Enter", "Enter"]

    def test_press_combo_sets_modifiers(self):
        browser, ws = _make_browser({"Input.dispatchKeyEvent": {}})
        browser.press("ctrl+s")
        down = next(m["params"] for m in ws.sent
                    if m["method"] == "Input.dispatchKeyEvent")
        assert down["key"] == "s"
        assert down["modifiers"] == 2


class TestActions:
    def _browser_with_console(self):
        browser, _ws = _make_browser({
            "Runtime.evaluate": {"result": {"value": []}},
        })
        browser.session.console_log.append("hello from page")
        return browser

    def test_get_images(self):
        browser, _ws = _make_browser({
            "Runtime.evaluate": {"result": {"value": [
                {"n": 0, "src": "https://x/a.png", "alt": "A"},
            ]}},
        })
        out = get_images(browser)
        assert "https://x/a.png" in out

    def test_console_output_and_clear(self):
        browser = self._browser_with_console()
        assert "hello from page" in console_output(browser)
        # clear=True reads AND clears in one call...
        assert console_output(browser, clear=True) == "hello from page"
        # ...so the next read is empty.
        assert console_output(browser) == "No console messages."
        assert browser.session.console_log == []

    def test_dialog_state_and_handle(self):
        browser, ws = _make_browser({"Page.handleJavaScriptDialog": {}})
        browser.session.dialog = {"type": "confirm", "message": "Proceed?"}
        assert "Proceed?" in dialog_state(browser)
        out = handle_dialog(browser, accept=False)
        assert "Dismissed" in out
        assert browser.session.dialog is None
        assert ws.sent[0]["params"]["accept"] is False
