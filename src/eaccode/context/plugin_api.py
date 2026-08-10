"""Minimal plugin API (Phase I.12) — the extension seam for context plugins.

A plugin is a single ``.py`` file in the plugins directory with a
``setup(api)`` function. Inside ``setup`` the plugin registers tools and
slash commands; eaccode wires them into the tool registry and the
command registry at startup.

Handler signatures:
- tool:  ``handler(args: dict, ctx: ToolContext) -> ToolResult | str``
         (sync or async)
- slash: ``handler(arg: str) -> str`` — pure text in, message out; the UI
         layer adapts it to the app object.

Plugin ``setup`` runs at most once per process (engine instance is
cached per plugins directory).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from eaccode.tools.base import ToolResult

# A handler may be sync or async and may return a ToolResult or plain text.
ToolHandler = Callable[..., ToolResult | str | Awaitable[ToolResult | str]]
SlashHandler = Callable[[str], str]


@dataclass
class PluginToolSpec:
    """A tool registered by a plugin, wrapped into a Tool by the engine."""

    name: str
    description: str
    handler: ToolHandler
    # name -> (python type, description); empty = no arguments
    parameters: dict[str, tuple[type, str]] = field(default_factory=dict)
    requires_permission: bool = False


@dataclass
class PluginSlashSpec:
    """A slash command registered by a plugin (category shown in /help)."""

    name: str
    description: str
    handler: SlashHandler
    category: str = "Plugins"


class PluginAPI:
    """Handle passed to a plugin's ``setup(api)``."""

    def __init__(self, plugin_name: str) -> None:
        self.plugin_name = plugin_name
        self.tools: list[PluginToolSpec] = []
        self.slash_commands: list[PluginSlashSpec] = []

    def register_tool(
        self,
        name: str,
        description: str,
        handler: ToolHandler,
        parameters: dict[str, tuple[type, str]] | None = None,
        requires_permission: bool = False,
    ) -> None:
        """Register a tool exposed to the agent.

        ``parameters`` maps argument names to ``(python type, description)``
        — e.g. ``{"name": (str, "file name")}``. Supported types: str,
        int, float, bool, and list[str].
        """
        if not name or not name.isidentifier():
            raise ValueError(f"Plugin {self.plugin_name}: invalid tool name {name!r}")
        self.tools.append(
            PluginToolSpec(
                name=name,
                description=description,
                handler=handler,
                parameters=parameters or {},
                requires_permission=requires_permission,
            )
        )

    def register_slash_command(
        self,
        name: str,
        description: str,
        handler: SlashHandler,
        category: str = "Plugins",
    ) -> None:
        """Register a slash command (canonical name without the leading slash)."""
        name = name.lstrip("/")
        if not name:
            raise ValueError(f"Plugin {self.plugin_name}: empty slash-command name")
        self.slash_commands.append(
            PluginSlashSpec(name=name, description=description,
                            handler=handler, category=category)
        )
