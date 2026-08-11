"""cua-driver client (Phase I.5) — full desktop + typed-browser action surface.

cua-driver is a separate binary speaking the OS accessibility API; this
module is the Python client. One JSON command per invocation on stdin,
one JSON reply on stdout:

    {"action": "capture", "params": {"mode": "som", "app": "Safari"}}
    → {"ok": true, "elements": [{"n": 1, "role": "button", ...}]}

``_run_driver`` is the only IO boundary — tests replace it with a fake.
The binary is located via ``$EACCODE_CUA_DRIVER`` or ``cua-driver`` on
PATH; ``eaccode computer install`` sets it up.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

# Permission semantics per action family (surfaced to the tool layer):
# capture/list_* are read-only; everything else mutates the desktop.
READ_ONLY_ACTIONS = frozenset({"capture", "list_apps", "list_windows",
                               "cua_browser_state", "cua_browser_prepare"})
# Actions that need their own approval scope (Hermes parity).
SENSITIVE_ACTIONS = frozenset({"cua_browser_existing_profile",
                               "bring_to_front", "foreground"})


def find_driver() -> Path | None:
    """Resolve the cua-driver binary ($EACCODE_CUA_DRIVER or PATH)."""
    override = os.environ.get("EACCODE_CUA_DRIVER")
    if override and Path(override).is_file():
        return Path(override)
    found = shutil.which("cua-driver")
    return Path(found) if found else None


def driver_available() -> bool:
    return find_driver() is not None


def _run_driver(command: dict, timeout: float = 60.0) -> dict:
    """Send one JSON command to cua-driver and parse the JSON reply.

    Raises FileNotFoundError with a setup hint when the driver is
    missing, RuntimeError on protocol/exit failures.
    """
    driver = find_driver()
    if driver is None:
        raise FileNotFoundError(
            "cua-driver not found — run `eaccode computer install` "
            "(or set EACCODE_CUA_DRIVER to the binary path)"
        )
    proc = subprocess.run(
        [str(driver)],
        input=json.dumps(command),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"cua-driver exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        )
    try:
        reply = json.loads(proc.stdout)
    except ValueError as e:
        raise RuntimeError(f"cua-driver returned non-JSON output: {e}") from e
    if not reply.get("ok", True):
        raise RuntimeError(f"cua-driver error: {reply.get('error', 'unknown')}")
    return reply


def _dispatch(action: str, **params) -> dict:
    return _run_driver({"action": action, "params": params})


# ---------------------------------------------------------------- desktop

def cua_capture(mode: str = "som", app: str | None = None, pid: int | None = None,
                window_id: str | None = None, max_elements: int = 100) -> dict:
    """Screen capture: som (numbered overlays + AX tree), vision (plain
    screenshot) or ax (accessibility tree only)."""
    return _dispatch("capture", mode=mode, app=app, pid=pid,
                     window_id=window_id, max_elements=max_elements)


def cua_click(element: int | None = None, coordinate: list[int] | None = None,
              button: str = "left", modifiers: list[str] | None = None,
              delivery: str = "background") -> dict:
    return _dispatch("click", element=element, coordinate=coordinate,
                     button=button, modifiers=modifiers, delivery=delivery)


def cua_double_click(element: int | None = None, coordinate: list[int] | None = None,
                     modifiers: list[str] | None = None) -> dict:
    return _dispatch("double_click", element=element, coordinate=coordinate,
                     modifiers=modifiers)


def cua_right_click(element: int | None = None, coordinate: list[int] | None = None,
                    modifiers: list[str] | None = None) -> dict:
    return _dispatch("right_click", element=element, coordinate=coordinate,
                     modifiers=modifiers)


def cua_middle_click(element: int | None = None, coordinate: list[int] | None = None,
                     modifiers: list[str] | None = None) -> dict:
    return _dispatch("middle_click", element=element, coordinate=coordinate,
                     modifiers=modifiers)


def cua_drag(from_element: int | None = None, to_element: int | None = None,
             from_coordinate: list[int] | None = None,
             to_coordinate: list[int] | None = None) -> dict:
    return _dispatch("drag", from_element=from_element, to_element=to_element,
                     from_coordinate=from_coordinate, to_coordinate=to_coordinate)


def cua_scroll(direction: str, amount: int = 3) -> dict:
    return _dispatch("scroll", direction=direction, amount=amount)


def cua_type(text: str) -> dict:
    return _dispatch("type", text=text)


def cua_key(combo: str) -> dict:
    return _dispatch("key", combo=combo)


def cua_set_value(label: str, value: str) -> dict:
    return _dispatch("set_value", label=label, value=value)


def cua_wait(seconds: float) -> dict:
    return _dispatch("wait", seconds=min(seconds, 30.0))


def cua_list_apps() -> dict:
    return _dispatch("list_apps")


def cua_list_windows(app: str | None = None) -> dict:
    return _dispatch("list_windows", app=app)


def cua_focus_app(app: str, raise_window: bool = False) -> dict:
    return _dispatch("focus_app", app=app, raise_window=raise_window)


def cua_capture_after(mode: str = "som", **action_params) -> dict:
    """Run an action, then capture for verification (single driver call)."""
    return _dispatch("capture_after", mode=mode, action=action_params)


# ------------------------------------------------------- typed-browser route

def cua_browser_state(query: str | None = None, scope_ref: str | None = None,
                      continuation: str | None = None) -> dict:
    """Semantic_v2/dom_refs_v1 snapshot of the browser page."""
    return _dispatch("cua_browser_state", query=query, scope_ref=scope_ref,
                     continuation=continuation)


def cua_browser_prepare(profile_mode: str = "isolated_new",
                        profile_name: str | None = None,
                        allow_launch: bool = True) -> dict:
    """Prepare a browser profile: isolated_new | isolated_named | existing_profile."""
    return _dispatch("cua_browser_prepare", profile_mode=profile_mode,
                     profile_name=profile_name, allow_launch=allow_launch)


def cua_browser_navigate(url: str, tab_id: str | None = None) -> dict:
    return _dispatch("cua_browser_navigate", url=url, tab_id=tab_id)


def cua_browser_click(ref: str | None = None, x: int | None = None,
                      y: int | None = None) -> dict:
    return _dispatch("cua_browser_click", ref=ref, x=x, y=y)


def cua_browser_type(text: str, mode: str = "insert_text") -> dict:
    """insert_text | keystrokes"""
    return _dispatch("cua_browser_type", text=text, mode=mode)


def cua_browser_pointer(action: str, x: int = 0, y: int = 0,
                        to_x: int | None = None, to_y: int | None = None,
                        delta_x: int = 0, delta_y: int = 0) -> dict:
    """hover | right_click | double_click | scroll | drag"""
    return _dispatch("cua_browser_pointer", action=action, x=x, y=y,
                     to_x=to_x, to_y=to_y, delta_x=delta_x, delta_y=delta_y)


def cua_browser_dialog(action: str = "inspect") -> dict:
    """inspect | accept | dismiss"""
    return _dispatch("cua_browser_dialog", action=action)


def cua_browser_set_input_files(paths: list[str], ref: str | None = None) -> dict:
    return _dispatch("cua_browser_set_input_files", paths=paths, ref=ref)


def cua_browser_download(destination_root: str) -> dict:
    return _dispatch("cua_browser_download", destination_root=destination_root)
