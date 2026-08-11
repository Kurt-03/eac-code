"""Default tool registry factory — one place to wire all built-in tools.

Phase I.0: tools are grouped into toolsets (mirroring Hermes'
CONFIGURABLE_TOOLSETS). ``build_default_registry`` accepts
``enabled_toolsets`` so the user can turn whole groups on/off via
``eaccode config toolsets`` without touching code.
"""

from __future__ import annotations

from eaccode.tools.base import Tool, ToolRegistry

# Toolset key → tool names (Hermes CONFIGURABLE_TOOLSETS pattern).
# "web" also carries web_fetch (eaccode's version of web_extract's HTTP layer).
TOOLSETS: dict[str, set[str]] = {
    "web": {"web_search", "web_fetch", "web_extract"},
    "terminal": {"bash", "process"},
    "file": {"read", "write", "edit", "glob", "grep", "search_files"},
    "code_execution": {"execute_code"},
    "skills": {"skill_create", "skill_patch", "skill_list", "skill_delete",
               "skill_write_file", "skill_remove_file"},
    "todo": {"todo_write"},
    "memory": {"memory_remember", "memory_recall", "memory_forget",
               "memory_edit"},
    "session_search": {"session_search"},
    "clarify": {"clarify"},
    "delegation": {"delegate_task"},
    "cronjob": {"cronjob"},
    "vision": {"vision_analyze", "video_analyze"},
    "browser": {"browser"},
    "computer_use": {"computer_use", "computer_use_capture"},
}

# Default-on toolsets (everything except niche/opt-in ones).
DEFAULT_TOOLSETS: set[str] = {
    "web", "terminal", "file", "code_execution", "skills", "todo",
    "memory", "session_search", "clarify", "delegation", "cronjob",
    "vision", "browser", "computer_use",
}


def _all_tools() -> list[Tool]:
    from eaccode.config.paths import EaccodePaths
    from eaccode.context.engine import get_engine
    from eaccode.memory.memory_tools import (
        MemoryEditTool,
        MemoryForgetTool,
        MemoryRecallTool,
        MemoryRememberTool,
    )
    from eaccode.memory.skill_tools import (
        SkillCreateTool,
        SkillDeleteTool,
        SkillListTool,
        SkillPatchTool,
        SkillRemoveFileTool,
        SkillWriteFileTool,
    )
    from eaccode.tools.builtin.bash import BashTool
    from eaccode.tools.builtin.browser import BrowserTool
    from eaccode.tools.builtin.clarify import ClarifyTool
    from eaccode.tools.builtin.computer_use import (
        ComputerUseCaptureTool,
        ComputerUseTool,
    )
    from eaccode.tools.builtin.cronjob import CronjobTool
    from eaccode.tools.builtin.delegate import DelegateTool
    from eaccode.tools.builtin.edit import EditTool
    from eaccode.tools.builtin.execute_code import ExecuteCodeTool
    from eaccode.tools.builtin.glob import GlobTool
    from eaccode.tools.builtin.process import ProcessTool
    from eaccode.tools.builtin.read import ReadTool
    from eaccode.tools.builtin.search_files import SearchFilesTool
    from eaccode.tools.builtin.todo import TodoWriteTool
    from eaccode.tools.builtin.tool_search import ToolSearchTool
    from eaccode.tools.builtin.vision import VideoAnalyzeTool, VisionAnalyzeTool
    from eaccode.tools.builtin.web_extract import WebExtractTool
    from eaccode.tools.builtin.web_search import WebSearchTool
    from eaccode.tools.builtin.write import WriteTool

    return [
        ReadTool(),
        WriteTool(),
        EditTool(),
        BashTool(),
        GlobTool(),
        TodoWriteTool(),
        SkillCreateTool(),
        SkillPatchTool(),
        SkillListTool(),
        SkillDeleteTool(),
        SkillWriteFileTool(),
        SkillRemoveFileTool(),
        ClarifyTool(),
        ExecuteCodeTool(),
        DelegateTool(),
        MemoryRememberTool(),
        MemoryRecallTool(),
        MemoryForgetTool(),
        MemoryEditTool(),
        CronjobTool(store_path=EaccodePaths().cron_db),
        SearchFilesTool(),
        WebExtractTool(),
        WebSearchTool(),  # G.6
        ToolSearchTool(),  # H.17
        ProcessTool(),
        VisionAnalyzeTool(),
        VideoAnalyzeTool(),
        BrowserTool(),
        ComputerUseTool(),
        ComputerUseCaptureTool(),
        # Phase I.12: plugin-registered runtime tools (context engine).
        *get_engine(EaccodePaths().plugins_dir).build_tools(),
    ]


def build_default_registry(
    allowed_tools: list[str] | None = None,
    enabled_toolsets: list[str] | None = None,
) -> ToolRegistry:
    """Registry with all built-in tools, optionally filtered.

    ``allowed_tools`` — whitelist of tool names (headless/--allowed-tools).
    ``enabled_toolsets`` — toolset keys; when given, only tools whose
    toolset is enabled are registered (default: DEFAULT_TOOLSETS).
    """
    reg = ToolRegistry()
    tools = _all_tools()

    if enabled_toolsets is not None:
        enabled = set(enabled_toolsets)
        keep = set()
        for ts, names in TOOLSETS.items():
            if ts in enabled:
                keep |= names
        # context_engine tools are registered at runtime by plugins; the
        # toolset has no static names, so nothing to filter here.
        tools = [t for t in tools if t.name in keep]

    if allowed_tools is not None:
        # C.2: wildcard whitelists are allowed (e.g. "memory_*" for the
        # background-review agent).
        from fnmatch import fnmatch

        tools = [
            t for t in tools
            if any(fnmatch(t.name, pat) for pat in allowed_tools)
        ]

    for tool in tools:
        reg.register(tool)
    # H.17: the tool_search lookup sees the final registry.
    from eaccode.tools.builtin.tool_search import set_registry_lookup

    set_registry_lookup(lambda: reg)
    return reg
