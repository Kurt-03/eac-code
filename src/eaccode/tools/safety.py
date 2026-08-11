"""File safety (Phase A.1) — protect eaccode's own state from the agent.

The agent must never write into its own config/data/cache directories
(providers.yaml holds API keys — we already saw a test overwrite the real
config once) and must not read credential files. Mirrors the Hermes
file_safety idea (write-denied paths, read blocks), scoped to eaccode.
"""
from __future__ import annotations

from pathlib import Path

_BLOCKED_FILENAMES = {".env", "providers.yaml", "credentials", "secrets.txt",
                      "allowlist.json", "mcp.yaml"}
_BLOCKED_SUFFIXES = {".pem", ".key", ".p12"}


def _eaccode_dirs() -> set[Path]:
    from eaccode.config.paths import EaccodePaths

    p = EaccodePaths()
    dirs = {p.config_dir, p.data_dir, p.cache_dir}
    # H.20: the eaccode package itself (site-packages or repo src/) —
    # the agent must not rewrite its own implementation.
    dirs.add(Path(__file__).resolve().parent.parent)
    return dirs


def is_write_denied(path: Path) -> Path | None:
    """Return the protected directory if *path* lies inside it, else None."""
    resolved = path.resolve()
    for base in _eaccode_dirs():
        try:
            resolved.relative_to(base.resolve())
            return base
        except ValueError:
            continue
    return None


def is_read_blocked(path: Path) -> bool:
    """Credential files must never be read into the conversation context."""
    name = path.name
    if name in _BLOCKED_FILENAMES or name.lower() in _BLOCKED_FILENAMES:
        return True
    if path.suffix.lower() in _BLOCKED_SUFFIXES:
        return True
    # keys look like: sk-..., AKIA..., ghp_... — block files whose name
    # contains "key" or "secret" (but not the project's own code)
    lowered = name.lower()
    return ("key" in lowered or "secret" in lowered) and lowered.endswith(
        (".txt", ".yaml", ".yml", ".json", ".toml", ".env")
    )


def write_denied_error(path: Path) -> str:
    base = is_write_denied(path)
    if base:
        return (
            f"Write denied: '{path}' is inside eaccode's own directory "
            f"({base}) — the agent must not modify its configuration, "
            "credentials, or session data."
        )
    return ""


def read_blocked_error(path: Path) -> str:
    if is_read_blocked(path):
        return (
            f"Read blocked: '{path}' looks like a credential file. "
            "Credentials must never enter the conversation context."
        )
    return ""
