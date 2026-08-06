"""XDG-compliant path resolution for eaccode (Task 1.1)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import PlatformDirs


def _xdg_or_default(env_var: str, platform_dir: str) -> Path:
    """Honor XDG env var when set (also on Windows), otherwise platform default."""
    override = os.environ.get(env_var)
    if override:
        return Path(override) / "eaccode"
    if os.name == "nt":
        # platformdirs doubles the app name on Windows (eaccode\\eaccode) —
        # so build directly: %LOCALAPPDATA%\\eaccode
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local / "eaccode"
    dirs = PlatformDirs(appname="eaccode", appauthor=None, ensure_exists=True)
    return Path(getattr(dirs, platform_dir))


@dataclass(frozen=True)
class EaccodePaths:
    """All eaccode directories and files in one place.

    Resolved via platformdirs (XDG on Linux/macOS, %APPDATA% on Windows);
    directories are created on instantiation.
    """

    config_dir: Path
    data_dir: Path
    cache_dir: Path
    sessions_dir: Path
    memory_dir: Path
    skills_dir: Path
    providers_file: Path
    settings_file: Path

    def __init__(self) -> None:
        cfg = _xdg_or_default("XDG_CONFIG_HOME", "user_config_dir")
        dat = _xdg_or_default("XDG_DATA_HOME", "user_data_dir")
        cache = _xdg_or_default("XDG_CACHE_HOME", "user_cache_dir")
        object.__setattr__(self, "config_dir", cfg)
        object.__setattr__(self, "data_dir", dat)
        object.__setattr__(self, "cache_dir", cache)
        object.__setattr__(self, "sessions_dir", dat / "sessions")
        object.__setattr__(self, "memory_dir", dat / "memory")
        object.__setattr__(self, "skills_dir", cfg / "skills")
        object.__setattr__(self, "providers_file", cfg / "providers.yaml")
        object.__setattr__(self, "settings_file", cfg / "eaccode.yaml")
        for d in (cfg, dat, cache, self.sessions_dir, self.memory_dir, self.skills_dir):
            d.mkdir(parents=True, exist_ok=True)
