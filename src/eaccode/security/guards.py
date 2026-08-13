"""Tool guards (H.11/H.20/H.21/H.22) — safety helpers for tools & loop.

- ``safe_url``        — only http/https URLs (H.11)
- ``is_protected_path`` — eaccode install + credential files (H.20/H.22)
- ``is_system_path``   — system dirs that must never be written (Plan 224)
- ``is_instruction_file`` — AGENTS.md, CLAUDE.md etc. always ask (Plan 229)
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


# Plan 224-228 — Hermes-style system path denylist. These prefixes
# never get a confirmation prompt; the tool call is rejected outright
# with a hint that the user should run the command themselves in a
# terminal. The list deliberately does NOT cover everything under
# /private/var (Plan 225) — macOS parks $TMPDIR there.
_SENSITIVE_PATH_PREFIXES: tuple[str, ...] = (
    # Linux
    "/etc/", "/boot/", "/usr/lib/systemd/", "/var/run/",
    # macOS — exact sub-paths only, not whole /private/var
    "/private/etc/", "/private/var/db/", "/private/var/root/",
    # Windows — case-insensitive in matching code below
    "C:/Windows/", "C:/Program Files/", "C:/Program Files (x86)/",
    "C:/ProgramData/",
)

# Exact docker socket paths (Plan 226). These are files, not dirs.
_SENSITIVE_EXACT_PATHS: tuple[str, ...] = (
    "/var/run/docker.sock",
    "/run/docker.sock",
)


def _normalize_for_match(path: Path) -> str:
    """Lower-case forward-slash string for prefix matching.

    On Windows, Path comparison with ``\\`` is finicky; we normalize to
    POSIX form and lowercase so prefix checks work consistently.
    """
    return str(path).replace("\\", "/").lower()


def is_system_path(path: Path) -> bool:
    """True if *path* lives under a system directory that must never be
    written, deleted, or in-place-edited. Rejected outright — Plan 224.

    The eaccode config dir itself is its own thing (see ``is_protected_path``);
    this function focuses on *external* system paths so we don't trip
    on the user's own machine config.
    """
    try:
        resolved = path.resolve()
    except OSError:
        return False
    norm = _normalize_for_match(resolved)
    for prefix in _SENSITIVE_PATH_PREFIXES:
        # Strip the trailing slash so "/etc" also matches "/etc/passwd";
        # a literal "/etc/" prefix would miss the bare directory.
        bare = prefix.rstrip("/").lower()
        if norm == bare or norm.startswith(bare + "/"):
            return True
    if norm in {p.lower() for p in _SENSITIVE_EXACT_PATHS}:
        return True
    return False


# Plan 229-234 — Hermes-style instruction-file denylist. These files
# always require a confirmation prompt, even under bypass/yolo mode.
# A poisoned instruction file survives the turn and contaminates every
# future session. Basenames match in any directory because the agent
# may read a file from anywhere on disk.
_PROTECTED_INSTRUCTION_BASENAMES: frozenset[str] = frozenset({
    # Hermes originals
    "agents.md", "claude.md", "soul.md", ".cursorrules",
    # eaccode-specific — match the names our memory layer writes.
    "eaccode.md", "user.md", "memory.md",
})


def is_instruction_file(path: Path) -> bool:
    """True if *path* is an instruction file the agent must always ask
    about before reading or writing.

    ``is_instruction_file`` returns True for ANY path whose basename
    matches the protected set, regardless of where it lives. Callers
    use this to force the permission gate even when yolo/mode=off is on.
    """
    return path.name.lower() in _PROTECTED_INSTRUCTION_BASENAMES


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
