"""Context engine (Phase I.12) — loads plugins and wires their tools.

Plugins live in the eaccode plugins directory (``plugins_dir`` from
``EaccodePaths``). Each ``*.py`` file is imported and its ``setup(api)``
is called with a :class:`~eaccode.context.plugin_api.PluginAPI` handle.
Broken plugins never break eaccode: import/setup errors are collected and
reported, the other plugins still load.

The engine instance is cached per plugins directory, so the tool registry
(factory) and the REPL (slash commands) share one load — ``setup`` runs
exactly once per process.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, create_model

from eaccode.context.plugin_api import (
    PluginAPI,
    PluginSlashSpec,
    PluginToolSpec,
)
from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult

logger = logging.getLogger(__name__)

_ENGINES: dict[str, ContextEngine] = {}

# Allowed parameter types for plugin tools (name -> pydantic type).
_PARAM_TYPES: dict[type, type] = {
    str: str,
    int: int,
    float: float,
    bool: bool,
    list: list[str],
}


class PluginTool(Tool):
    """Runtime Tool wrapper around a PluginToolSpec (instance attributes)."""

    tool_class = ToolClass.MUTATING

    def __init__(self, spec: PluginToolSpec) -> None:
        self._spec = spec
        self.name = spec.name
        self.description = spec.description
        self.requires_permission = spec.requires_permission
        fields = {
            fname: (ftype, Field(description=fdesc))
            for fname, (ftype, fdesc) in spec.parameters.items()
        }
        self.input_model = create_model(
            f"PluginInput_{spec.name}", **fields
        ) if fields else _EmptyInput

    async def run(self, input: BaseModel, ctx: ToolContext) -> ToolResult:
        result = self._spec.handler(input.model_dump(), ctx)
        if isinstance(result, ToolResult):
            return result
        if hasattr(result, "__await__"):
            result = await result
        if isinstance(result, ToolResult):
            return result
        return ToolResult(content=str(result))


class _EmptyInput(BaseModel):
    pass


class ContextEngine:
    def __init__(self, plugins_dir: Path) -> None:
        self.plugins_dir = Path(plugins_dir)
        self._tools: list[PluginToolSpec] = []
        self._slash: list[PluginSlashSpec] = []
        self._errors: list[tuple[str, str]] = []
        self._loaded: list[str] = []

    # ------------------------------------------------------------- loading

    def load(self) -> list[str]:
        """Import every ``*.py`` plugin; returns loaded plugin names."""
        if not self.plugins_dir.is_dir():
            return []
        for path in sorted(self.plugins_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            self._load_one(path)
        return self._loaded

    def _load_one(self, path: Path) -> None:
        name = path.stem
        try:
            module = self._import(path, name)
            setup = getattr(module, "setup", None)
            if setup is None:
                self._errors.append(
                    (name, "plugin has no setup(api) function — ignored")
                )
                return
            api = PluginAPI(name)
            setup(api)
            self._tools.extend(api.tools)
            self._slash.extend(api.slash_commands)
            self._loaded.append(name)
        except Exception as e:  # a broken plugin must not break eaccode
            self._errors.append((name, f"{type(e).__name__}: {e}"))
            logger.warning("Plugin %s failed to load: %s", name, e)

    @staticmethod
    def _import(path: Path, name: str) -> Any:
        spec = importlib.util.spec_from_file_location(f"eaccode_plugin_{name}", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load plugin from {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    # ------------------------------------------------------------ accessors

    def tool_specs(self) -> list[PluginToolSpec]:
        return list(self._tools)

    def slash_specs(self) -> list[PluginSlashSpec]:
        return list(self._slash)

    def errors(self) -> list[tuple[str, str]]:
        return list(self._errors)

    def build_tools(self) -> list[Tool]:
        return [PluginTool(spec) for spec in self._tools]


def get_engine(plugins_dir: Path) -> ContextEngine:
    """Return the (cached) engine for a plugins directory — setup runs once."""
    key = str(plugins_dir)
    engine = _ENGINES.get(key)
    if engine is None:
        engine = ContextEngine(plugins_dir)
        engine.load()
        _ENGINES[key] = engine
    return engine
