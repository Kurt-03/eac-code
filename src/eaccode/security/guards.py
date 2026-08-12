"""Tool guards (H.11/H.20/H.21/H.22) — safety helpers for tools & loop.

- ``safe_url``        — only http/https URLs (H.11)
- ``is_protected_path`` — eaccode install + credential files (H.20/H.22)
- ``detect_injection``  — prompt-injection patterns in tool output (H.21)
- ``display_arguments`` — redacted + canonicalized args for the modal (H.1)
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# --------------------------------------------------------------- H.11


def safe_url(url: str) -> bool:
    """True for http/https URLs (blocks file:, data:, javascript:, ...)."""
    if not url or "://" not in url:
        return False
    scheme = url.split("://", 1)[0].lower()
    return scheme in ("http", "https")


# ----------------------------------------------------------- H.20/H.22


def is_protected_path(path: Path, workdir: Path | None = None) -> bool:
    """True when the path is eaccode's own install or a credential file.

    H.22: credential files (providers.yaml, .env, allowlist.json) are
    never readable by agent tools — keys only enter via the provider
    layer, and the user pastes them through the hidden CLI prompt.
    """
    try:
        resolved = path.resolve()
    except OSError:
        return False
    # E7 (audit): credential files are only sacred under eaccode's own
    # config dir — a project's legitimate .env is agent input, not a
    # secret to guard (the old code blocked every .env on disk).
    name = resolved.name.lower()
    if name in (".env", "providers.yaml", "allowlist.json", "mcp.yaml"):
        try:
            from eaccode.config.paths import EaccodePaths

            config_dir = EaccodePaths().config_dir.resolve()
        except Exception:
            config_dir = None
        if config_dir is not None:
            try:
                resolved.relative_to(config_dir)
                return True
            except ValueError:
                pass
    # The eaccode package install itself (H.20): the agent must not
    # rewrite its own source through tools.
    pkg = Path(__file__).resolve().parent.parent  # .../site-packages/eaccode
    try:
        resolved.relative_to(pkg)
        return True
    except ValueError:
        pass
    return False


# --------------------------------------------------------------- H.21

_INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?(previous|prior|above) instructions", re.I),
    re.compile(r"disregard (the )?(previous|above) (instructions|prompt)", re.I),
    re.compile(r"you are now (a )?(?:chatgpt|an? ?\w+ agent)[,.]", re.I),
    re.compile(r"pretend (you are|to be)", re.I),
    re.compile(r"forget (everything|all instructions)", re.I),
]


def detect_injection(text: str) -> list[str]:
    """Prompt-injection patterns found in *text* (empty list = clean)."""
    if not text:
        return []
    return [p.pattern for p in _INJECTION_PATTERNS if p.search(text)]


# ----------------------------------------------------------------- H.1


def display_arguments(tool_name: str, arguments: dict,
                      workdir: Path | None = None) -> dict:
    """Redacted + canonicalized arguments for permission display.

    Relative paths resolve against *workdir* so the modal shows what
    will actually be touched; credential-like values are masked.
    """
    from eaccode.security.redact import redact_dict

    out = redact_dict(arguments)
    path_key = (
        "path" if tool_name in ("read", "write", "edit")
        else "workdir" if tool_name == "bash" else None
    )
    if path_key and path_key in out and workdir is not None:
        raw = str(out[path_key])
        if not os.path.isabs(raw):
            from contextlib import suppress

            with suppress(OSError):
                out[path_key] = str((workdir / raw).resolve())
    return out
