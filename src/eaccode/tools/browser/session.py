"""CDP browser session (Phase I.7) — connect, navigate, snapshot, interact.

A full CDP stack over websocket-client, not a Playwright shortcut: the
agent talks Chrome DevTools Protocol directly. ``CdpBrowser`` wraps one
page target and exposes the Hermes-style surface — navigate, snapshot
(accessibility tree with refs), click by ref, type, press, scroll, back,
evaluate — while :mod:`eaccode.tools.browser.actions` adds get_images,
console, vision, dialogs and downloads on top.

Browser discovery/launch is best-effort: when no Chrome/Edge binary is
found the tool reports a clear setup hint instead of crashing.
"""

from __future__ import annotations

import json
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from eaccode._subprocess_compat import IS_WINDOWS, windows_detach_flags

DEFAULT_PORT = 9222
_SNAPSHOT_CAP = 100  # max elements surfaced per snapshot (Hermes parity)
_NAV_TIMEOUT_S = 10.0

# Common executable names per platform, best first.
_BROWSER_CANDIDATES: list[tuple[str, ...]] = [
    # Windows (Program Files + LOCALAPPDATA)
    (r"C:\Program Files\Google\Chrome\Application\chrome.exe",),
    (r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",),
    (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",),
    (r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",),
    # POSIX
    ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
     "microsoft-edge", "microsoft-edge-stable"),
]

_KEY_MAP = {
    "enter": "Enter", "return": "Enter", "escape": "Escape", "esc": "Escape",
    "tab": "Tab", "backspace": "Backspace", "delete": "Delete", "del": "Delete",
    "up": "ArrowUp", "arrowup": "ArrowUp", "down": "ArrowDown",
    "arrowdown": "ArrowDown", "left": "ArrowLeft", "arrowleft": "ArrowLeft",
    "right": "ArrowRight", "arrowright": "ArrowRight", "home": "Home",
    "end": "End", "pageup": "PageUp", "pagedown": "PageDown",
    "space": " ", " ": " ",
}

_MODIFIERS = {"ctrl": 2, "control": 2, "alt": 1, "shift": 8, "meta": 4, "cmd": 4, "super": 4}


def find_browser() -> Path | None:
    """First installed Chrome/Edge/Chromium binary, else None."""
    for candidates in _BROWSER_CANDIDATES:
        for name in candidates:
            path = shutil.which(name)
            if path:
                return Path(path)
            p = Path(name)
            if p.is_file():
                return p
    if IS_WINDOWS:
        local = Path(__import__("os").environ.get(
            "LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        for sub in ("Google/Chrome/Application/chrome.exe",
                    "Microsoft/Edge/Application/msedge.exe"):
            p = local / sub
            if p.is_file():
                return p
    return None


def launch_browser(port: int = DEFAULT_PORT, headless: bool = True,
                   user_data_dir: str | None = None) -> subprocess.Popen:
    """Start a fresh browser instance with the debug port open.

    Uses a private temp profile so the agent never touches the user's
    real browser profile. Returns the Popen handle (caller keeps it).
    """
    browser = find_browser()
    if browser is None:
        raise FileNotFoundError(
            "No Chrome/Edge/Chromium found — install one to use the browser tool"
        )
    profile = user_data_dir or tempfile.mkdtemp(prefix="eaccode-cdp-")
    cmd = [
        str(browser),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run", "--no-default-browser-check",
        "--disable-background-networking", "--disable-sync",
        "--disable-features=TranslateUI",
    ]
    if headless:
        cmd.append("--headless=new")
    kwargs: dict[str, Any] = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = windows_detach_flags()
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, **kwargs)


def _wait_for_endpoint(port: int, timeout: float = 10.0) -> bool:
    """Poll http://127.0.0.1:port/json/version until the browser answers."""
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version",
                                        timeout=1) as resp:
                return resp.status == 200
        except OSError:
            time.sleep(0.25)
    return False


class CdpSession:
    """One WebSocket connection to a page target (thread-safe send)."""

    def __init__(self, port: int = DEFAULT_PORT,
                 ws_factory: Callable[[str], Any] | None = None) -> None:
        self.port = port
        self._ws_factory = ws_factory  # DI seam for tests
        self._ws: Any = None
        self._next_id = 0
        self._lock = threading.Lock()
        self._incoming: queue.Queue[dict] = queue.Queue()
        self.console_log: list[str] = []
        self.dialog: dict | None = None

    # ------------------------------------------------------------ connect

    def connect(self) -> None:
        """Connect to the first page target on the debug port."""
        import urllib.request

        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json",
                                    timeout=3) as resp:
            targets = json.loads(resp.read().decode("utf-8"))
        page = next((t for t in targets if t.get("type") == "page"), None)
        if page is None:
            raise RuntimeError(f"No page target on port {self.port}")
        ws_url = page["webSocketDebuggerUrl"]
        if self._ws_factory is not None:
            self._ws = self._ws_factory(ws_url)
        else:
            import websocket

            self._ws = websocket.create_connection(ws_url, timeout=15)
        if hasattr(self._ws, "settimeout"):
            self._ws.settimeout(15)
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        """Background reader: responses → queue, events → state.

        Only this thread calls ``recv()`` — a WebSocket is not safe for
        concurrent reads, and a response must never be consumed by the
        wrong waiter.
        """
        while True:
            try:
                raw = self._ws.recv()
            except Exception:
                break
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if msg.get("id") is not None:
                self._incoming.put(msg)
            else:
                self._handle_event(msg)

    def _handle_event(self, msg: dict) -> None:
        method = msg.get("method")
        params = msg.get("params", {})
        if method == "Runtime.consoleAPICalled":
            values = [
                a.get("value", a.get("description", ""))
                for a in params.get("args", [])
            ]
            self.console_log.append(" ".join(str(v) for v in values))
        elif method == "Runtime.exceptionThrown":
            exc = params.get("exceptionDetails", {})
            self.console_log.append(f"EXCEPTION: {exc.get('text', '')}")
        elif method == "Page.javascriptDialogOpening":
            self.dialog = params

    # ---------------------------------------------------------------- send

    def send(self, method: str, params: dict | None = None,
             timeout: float = 15.0) -> dict:
        """Send a CDP command; raises RuntimeError on protocol errors."""
        with self._lock:
            self._next_id += 1
            msg_id = self._next_id
            payload = json.dumps({"id": msg_id, "method": method,
                                  "params": params or {}})
            self._ws.send(payload)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                msg = self._incoming.get(timeout=0.5)
            except queue.Empty:
                continue
            if msg.get("id") == msg_id:
                if "error" in msg:
                    err = msg["error"]
                    raise RuntimeError(f"CDP {method}: {err.get('message', err)}")
                return msg.get("result", {})
        raise TimeoutError(f"CDP {method} timed out after {timeout}s")

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._ws.close()


class CdpBrowser:
    """High-level page automation over one CdpSession."""

    def __init__(self, session: CdpSession) -> None:
        self.session = session
        self._elements: list[dict] = []  # last snapshot: {ref, role, name, node}

    # ------------------------------------------------------------ lifecycle

    @classmethod
    def connect(cls, port: int = DEFAULT_PORT,
                ws_factory: Callable[[str], Any] | None = None) -> CdpBrowser:
        session = CdpSession(port, ws_factory=ws_factory)
        session.connect()
        return cls(session)

    # ------------------------------------------------------------ actions

    def navigate(self, url: str) -> dict:
        self.session.send("Page.navigate", {"url": url})
        deadline = time.monotonic() + _NAV_TIMEOUT_S
        while time.monotonic() < deadline:
            try:
                ready = self.evaluate("document.readyState")
            except RuntimeError:
                ready = "loading"
            if ready == "complete":
                break
            time.sleep(0.2)
        return {"url": url, "status": "loaded"}

    def snapshot(self, max_elements: int = _SNAPSHOT_CAP) -> str:
        """Accessibility tree as a text list with @e{n} refs."""
        tree = self.session.send("Accessibility.getFullAXTree", {})
        nodes = tree.get("nodes", [])
        self._elements = []
        lines: list[str] = []
        for node in nodes:
            if len(self._elements) >= max_elements:
                break
            role = (node.get("role") or {}).get("value", "")
            name = (node.get("name") or {}).get("value", "")
            if not name and role in ("none", "Unknown"):
                continue
            backend = node.get("backendDOMNodeId")
            if backend is None:
                continue
            ref = len(self._elements) + 1
            self._elements.append({"ref": ref, "role": role, "name": name,
                                   "node": backend})
            lines.append(f"[@e{ref}] {role}: {name}")
        if not lines:
            return "(no accessible elements)"
        return "\n".join(lines)

    def click(self, ref: str | int) -> dict:
        idx = self._ref_index(ref)
        if idx is None:
            raise ValueError(f"Unknown element ref {ref!r} — run snapshot first")
        x, y = self._element_center(self._elements[idx]["node"])
        self.session.send("Input.dispatchMouseEvent",
                          {"type": "mousePressed", "x": x, "y": y,
                           "button": "left", "clickCount": 1})
        self.session.send("Input.dispatchMouseEvent",
                          {"type": "mouseReleased", "x": x, "y": y,
                           "button": "left", "clickCount": 1})
        return {"clicked": str(ref), "at": [x, y]}

    def type(self, text: str) -> dict:
        self.session.send("Input.insertText", {"text": text})
        return {"typed": len(text), "chars": text[:40]}

    def press(self, key: str) -> dict:
        mapped = _KEY_MAP.get(key.strip().lower(), key)
        if mapped in _KEY_MAP.values() or len(mapped) == 1:
            self.session.send("Input.dispatchKeyEvent",
                              {"type": "keyDown", "key": mapped})
            self.session.send("Input.dispatchKeyEvent",
                              {"type": "keyUp", "key": mapped})
            return {"pressed": key}
        mods = _parse_modifiers(key)
        if mods is not None:
            name, mask = mods
            self.session.send("Input.dispatchKeyEvent",
                              {"type": "keyDown", "key": name,
                               "modifiers": mask})
            self.session.send("Input.dispatchKeyEvent",
                              {"type": "keyUp", "key": name,
                               "modifiers": mask})
            return {"pressed": key}
        raise ValueError(f"Unsupported key: {key!r}")

    def scroll(self, direction: str, amount: int = 3) -> dict:
        d = direction.lower()
        if d == "up":
            dx, dy = 0, -amount * 100
        elif d == "down":
            dx, dy = 0, amount * 100
        elif d == "left":
            dx, dy = -amount * 100, 0
        elif d == "right":
            dx, dy = amount * 100, 0
        else:
            raise ValueError(f"direction must be up/down/left/right, got {direction!r}")
        self.session.send("Input.dispatchMouseEvent",
                          {"type": "mouseWheel", "x": 0, "y": 0,
                           "deltaX": dx, "deltaY": dy})
        return {"scrolled": direction, "amount": amount}

    def back(self) -> dict:
        history = self.session.send("Page.getNavigationHistory", {})
        entries = history.get("entries", [])
        index = history.get("currentIndex", 0)
        if index <= 0 or not entries:
            return {"back": False, "reason": "no history"}
        target = entries[index - 1]["id"]
        self.session.send("Page.navigateToHistoryEntry", {"entryId": target})
        return {"back": True, "to": entries[index - 1].get("url", "")}

    def evaluate(self, expression: str) -> Any:
        result = self.session.send("Runtime.evaluate",
                                   {"expression": expression,
                                    "returnByValue": True})
        exc = result.get("exceptionDetails")
        if exc:
            raise RuntimeError(f"evaluate failed: {exc.get('text', '')}")
        return result.get("result", {}).get("value")

    def screenshot(self) -> str:
        """Base64 PNG data URL of the current viewport."""
        shot = self.session.send("Page.captureScreenshot", {"format": "png"})
        b64 = shot.get("data", "")
        if not b64:
            raise RuntimeError("captureScreenshot returned no data")
        return f"data:image/png;base64,{b64}"

    # ------------------------------------------------------------ helpers

    def _ref_index(self, ref: str | int) -> int | None:
        if isinstance(ref, str):
            ref = ref.lstrip("@").lstrip("e")
        try:
            n = int(ref)
        except (TypeError, ValueError):
            return None
        if 1 <= n <= len(self._elements):
            return n - 1
        return None

    def _element_center(self, backend_node_id: int) -> tuple[float, float]:
        box = self.session.send("DOM.getBoxModel",
                                {"backendNodeId": backend_node_id})
        quad = box.get("model", {}).get("content", [])
        if not quad:
            raise RuntimeError("Element has no box model (not visible?)")
        xs = quad[0::2]
        ys = quad[1::2]
        return sum(xs) / len(xs), sum(ys) / len(ys)


def _parse_modifiers(combo: str) -> tuple[str, int] | None:
    """'ctrl+s' → ('s', 2); None when the combo isn't modifier+key."""
    parts = combo.lower().split("+")
    if len(parts) < 2 or not parts[-1] or parts[-1] in _MODIFIERS:
        return None
    mask = 0
    for mod in parts[:-1]:
        if mod not in _MODIFIERS:
            return None
        mask |= _MODIFIERS[mod]
    key = _KEY_MAP.get(parts[-1], parts[-1])
    return key, mask
