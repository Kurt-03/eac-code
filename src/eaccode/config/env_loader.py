"""Env loader (E.6) — .env files without a new dependency.

Loads ``~/.eaccode/.env`` and ``<workdir>/.env`` (KEY=VALUE lines,
``#`` comments) into the process environment. Existing environment
variables win — a shell export can always override the file.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_files(*paths: Path) -> int:
    """Load KEY=VALUE pairs; returns the number of NEW variables set."""
    loaded = 0
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key or not value or key in os.environ:
                continue
            os.environ[key] = value
            loaded += 1
    return loaded


def global_env_file() -> Path:
    """~/.eaccode/.env — per-user secrets outside the repo."""
    from eaccode.config.paths import EaccodePaths

    return EaccodePaths().config_dir / ".env"
