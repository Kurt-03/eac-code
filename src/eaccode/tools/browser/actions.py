"""Browser auxiliary actions (Phase I.7) — media, console, dialogs, downloads.

These sit on top of :class:`~eaccode.tools.browser.session.CdpBrowser` and
cover the rest of the Hermes browser surface: image inventory, console
(error) readout, screenshot-based vision, JavaScript dialog handling, and
download directory control.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from eaccode.tools.browser.session import CdpBrowser


def get_images(browser: CdpBrowser) -> str:
    """List every <img> on the page: index, src, alt."""
    images = browser.evaluate(
        "Array.from(document.images).map((i, n) => "
        "({n, src: i.currentSrc || i.src, alt: i.alt}))"
    ) or []
    if not images:
        return "No images on the current page."
    lines = [f"{img.get('n', i)}. {img.get('src', '')}"
             + (f"  alt={img.get('alt')}" if img.get("alt") else "")
             for i, img in enumerate(images)]
    return "\n".join(lines)


def console_output(browser: CdpBrowser, clear: bool = False) -> str:
    """Collected console messages + JS exceptions since connect/last read."""
    messages = list(browser.session.console_log)
    if clear:
        browser.session.console_log.clear()
    if not messages:
        return "No console messages."
    return "\n".join(messages)


def vision_ask(browser: CdpBrowser, question: str) -> str:
    """Screenshot the viewport and ask the configured vision provider."""
    from eaccode.llm.aux_vision import ask_vision

    data_url = browser.screenshot()
    result = ask_vision(data_url, question)
    if result.is_error:
        return f"Vision failed: {result.content}"
    return result.content


def dialog_state(browser: CdpBrowser) -> str:
    """Current JavaScript dialog (alert/confirm/prompt) or 'none'."""
    dlg = browser.session.dialog
    if dlg is None:
        return "No dialog open."
    return (f"{dlg.get('type', 'dialog')}: {dlg.get('message', '')}"
            + (f"  (default prompt: {dlg.get('defaultPrompt', '')})"
               if dlg.get("defaultPrompt") else ""))


def handle_dialog(browser: CdpBrowser, accept: bool = True,
                  prompt_text: str | None = None) -> str:
    """Accept/dismiss the current dialog; returns its description."""
    dlg = browser.session.dialog
    if dlg is None:
        return "No dialog to handle."
    params = {"accept": accept}
    if prompt_text is not None:
        params["promptText"] = prompt_text
    browser.session.send("Page.handleJavaScriptDialog", params)
    browser.session.dialog = None
    return f"{'Accepted' if accept else 'Dismissed'}: {dlg.get('message', '')}"


def set_download_dir(browser: CdpBrowser, directory: str | Path) -> str:
    """Point the browser's download folder at *directory* (Browser.setDownloadBehavior)."""
    path = str(directory)
    browser.session.send(
        "Browser.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": path},
    )
    return f"Downloads will go to: {path}"


def screenshot_path(browser: CdpBrowser, out: Path) -> Path:
    """Save a viewport screenshot to a PNG file; returns the path."""
    data_url = browser.screenshot()
    raw = data_url.split(",", 1)[1]
    out.write_bytes(base64.b64decode(raw))
    return out


def dump_state(browser: CdpBrowser) -> str:
    """JSON state dump: url, title, element count, console length (debug)."""
    state = {
        "url": browser.evaluate("location.href"),
        "title": browser.evaluate("document.title"),
        "elements": len(browser._elements),
        "console_messages": len(browser.session.console_log),
        "dialog_open": browser.session.dialog is not None,
    }
    return json.dumps(state, indent=2)
