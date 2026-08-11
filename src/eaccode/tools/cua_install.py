"""cua-driver installer + doctor (Phase I.5) — Windows-first.

Installs the cua-driver binary (winget on Windows, brew on macOS, plain
download instructions elsewhere), verifies it, and repairs the Windows
autostart service when the driver was installed but its service is
missing/broken (port of Hermes' autostart repair, simplified).
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from eaccode.tools.cua import find_driver

# Package names per platform package manager.
_WINGET_ID = "cua-driver.cua-driver"  # best-effort; falls back to instructions


def driver_status() -> dict:
    """{installed, path, version} — version via `cua-driver --version`."""
    driver = find_driver()
    if driver is None:
        return {"installed": False, "path": None, "version": None}
    version: str | None = None
    try:
        proc = subprocess.run(
            [str(driver), "--version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
        version = proc.stdout.strip() or proc.stderr.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"installed": True, "path": str(driver), "version": version}


def install_cua_driver() -> str:
    """Install via the platform package manager; returns human-readable output."""
    if sys.platform == "win32":
        if shutil.which("winget"):
            proc = subprocess.run(
                ["winget", "install", "--id", _WINGET_ID, "--accept-source-agreements",
                 "--accept-package-agreements", "--silent"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=300,
            )
            if proc.returncode == 0:
                return "cua-driver installed via winget."
            return (
                "winget install failed "
                f"(rc={proc.returncode}): {proc.stderr.strip()[:200]}\n"
                "Install cua-driver manually and set EACCODE_CUA_DRIVER to its path."
            )
        return (
            "winget not found. Install cua-driver manually (see its GitHub "
            "releases) and set EACCODE_CUA_DRIVER to the binary path."
        )
    if sys.platform == "darwin":
        if shutil.which("brew"):
            proc = subprocess.run(["brew", "install", "cua-driver"],
                                  capture_output=True, text=True, timeout=300)
            if proc.returncode == 0:
                return "cua-driver installed via Homebrew."
    return (
        f"Manual install required on {sys.platform}: download cua-driver, "
        "put it on PATH, or set EACCODE_CUA_DRIVER."
    )


def _repair_windows_autostart() -> str | None:
    """Best-effort repair of the Windows autostart service.

    When a cua-driver service exists but is stopped/disabled, start it;
    when it is missing entirely, report the manual registration command.
    """
    if sys.platform != "win32":
        return None
    try:
        proc = subprocess.run(["sc", "query", "cua-driver"],
                              capture_output=True, text=True, timeout=15)
    except OSError:
        return None
    if "RUNNING" in proc.stdout:
        return None
    if "SERVICE_NAME" in proc.stdout:  # exists but not running
        subprocess.run(["sc", "start", "cua-driver"],
                       capture_output=True, timeout=15)
        return "cua-driver service was stopped — start attempted."
    return (
        "cua-driver Windows service not registered. Register it with:\n"
        "  sc create cua-driver binPath= \"<path-to-cua-driver> --service\" start= auto"
    )


def doctor() -> list[str]:
    """Run diagnostics; returns a list of findings (empty = all good)."""
    findings: list[str] = []
    status = driver_status()
    if not status["installed"]:
        findings.append("cua-driver binary not found. Run `eaccode computer install`.")
        return findings
    findings.append(f"cua-driver: {status['path']}"
                    + (f" (v{status['version']})" if status["version"] else ""))
    repair = _repair_windows_autostart()
    if repair:
        findings.append(repair)
    return findings
