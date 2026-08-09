"""Cross-platform clipboard (Phase G.4) — text copy on Windows/macOS/Linux.

Ported from Hermes' ``hermes_cli/clipboard.py`` text path. Windows uses
``clip.exe`` (always present); macOS uses ``pbcopy``; Linux tries
``wl-copy`` (Wayland) then ``xclip``/``xsel`` (X11). The REPL's old
``/copy`` was Windows-only — this makes it work everywhere.
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def _run(argv: list[str], data: bytes) -> bool:
    try:
        proc = subprocess.run(
            argv, input=data, capture_output=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return proc.returncode == 0
    except Exception:
        return False


def write_clipboard_text(text: str) -> bool:
    """Copy *text* to the system clipboard. Returns True on success."""
    if not text:
        return False
    data = text.encode("utf-8", errors="replace")

    if sys.platform == "win32":
        # clip.exe wants UTF-16LE; "utf-16" (with BOM) is the robust form.
        return _run(["clip"], text.encode("utf-16"))
    if sys.platform == "darwin":
        return _run(["pbcopy"], data)

    # Linux: Wayland first, then X11.
    if shutil.which("wl-copy"):
        return _run(["wl-copy"], data)
    for tool in ("xclip", "xsel"):
        if shutil.which(tool):
            args = ["xclip", "-selection", "clipboard"] if tool == "xclip" else ["xsel", "--clipboard", "--input"]
            return _run(args, data)
    return False


def clipboard_available() -> bool:
    """True when any clipboard backend exists on this platform."""
    if sys.platform in ("win32", "darwin"):
        return True
    return any(shutil.which(t) for t in ("wl-copy", "xclip", "xsel"))
