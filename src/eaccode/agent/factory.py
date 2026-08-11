"""Agent factory (DRY) — wires providers, tools, policy, and system prompt.

Both `eaccode run` and the REPL build their agent here, so project context
(EACCODE.md), auto-memory, and skills are injected the same way everywhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eaccode.agent.context import build_system_prompt
from eaccode.agent.loop import AgentConfig, AgentLoop
from eaccode.config.paths import EaccodePaths
from eaccode.config.providers import load_providers
from eaccode.config.settings import PermissionMode, Settings
from eaccode.llm.client import LLMClient
from eaccode.memory.project import discover_project_context
from eaccode.memory.skill_usage import record_use
from eaccode.memory.skills import discover_skills, skills_to_system_prompt_section
from eaccode.memory.store import MemoryStore
from eaccode.permissions.policy import PolicyEngine
from eaccode.permissions.rules import RuleSet
from eaccode.tools.factory import build_default_registry

# System-prompt cache (Phase D.2): the prompt has a stable structure
# (identity → rules → memory → skills → behavior) so providers can cache
# the prefix; memoizing the build keeps repeated constructions identical.
_prompt_cache: dict[tuple, SystemContext] = {}
_PROMPT_CACHE_MAX = 32

# A.6: above this many skills the static injection collapses into an index;
# trigger-matched skills are injected dynamically per turn by the loop.
SKILL_INDEX_THRESHOLD = 12


@dataclass
class SystemContext:
    system_prompt: str
    memory_facts: list[str]


def build_system_context(
    workdir: Path,
    *,
    skills_dirs: list[Path] | None = None,
    memory: MemoryStore | None = None,
    ignore_rules: bool = False,
    markdown_memory_dir: Path | None = None,
) -> SystemContext:
    """Compose the system prompt (sync — for CLI contexts without a loop)."""
    import asyncio

    return asyncio.run(
        build_system_context_async(
            workdir,
            skills_dirs=skills_dirs,
            memory=memory,
            ignore_rules=ignore_rules,
            markdown_memory_dir=markdown_memory_dir,
        )
    )


async def build_system_context_async(
    workdir: Path,
    *,
    skills_dirs: list[Path] | None = None,
    memory: MemoryStore | None = None,
    ignore_rules: bool = False,
    markdown_memory_dir: Path | None = None,
    skills_auto_load: bool = True,  # A.7: settings.skills.auto_load
) -> SystemContext:
    """Compose the system prompt from project rules + memory + skills.

    Async variant — the REPL runs inside Textual's event loop, where
    asyncio.run() is forbidden ("cannot be called from a running event loop").
    """
    project_rules = "" if ignore_rules else discover_project_context(workdir)
    memory_facts: list[str] = []
    if memory is not None and not ignore_rules:
        memory_facts = await memory.recall(MemoryStore.project_hash(workdir))
    # P0.3: markdown memory files (MEMORY.md / USER.md / SOUL.md) are
    # injected as their own sections, next to the JSONL facts.
    md_memory_section = _markdown_memory_section(workdir, markdown_memory_dir)
    skills = ""
    if skills_dirs and not ignore_rules and skills_auto_load:
        loaded = discover_skills(skills_dirs)
        # P0.4: injected skills count as a use — the curator's stale
        # signal needs real usage, not edit mtimes.
        for s in loaded:
            record_use(s.source)
        # A.6: large skill sets collapse into a compact index; the loop
        # injects trigger-matched skills dynamically per turn.
        if len(loaded) > SKILL_INDEX_THRESHOLD:
            from eaccode.memory.skill_triggers import build_skill_index

            skills = build_skill_index(loaded)
        else:
            skills = skills_to_system_prompt_section(loaded)
    # Phase H.2: workspace snapshot (git state + verify commands) —
    # computed per session so the cache key reflects the repo state.
    from eaccode.agent.workspace import build_coding_workspace_block

    workspace_block = "" if ignore_rules else build_coding_workspace_block(workdir)
    key = (
        str(workdir), project_rules, tuple(memory_facts), skills, ignore_rules,
        workspace_block, md_memory_section,
    )
    cached = _prompt_cache.get(key)
    if cached is not None:
        return cached
    prompt = build_system_prompt(
        project_rules=project_rules,
        memory_facts=memory_facts,
        md_memory_section=md_memory_section,
        skills=skills,
        workdir=str(workdir),
        workspace_block=workspace_block,
    )
    ctx = SystemContext(system_prompt=prompt, memory_facts=memory_facts)
    if len(_prompt_cache) >= _PROMPT_CACHE_MAX:
        _prompt_cache.clear()
    _prompt_cache[key] = ctx
    return ctx


def _markdown_memory_section(workdir: Path,
                             memory_dir: Path | None) -> str:
    """P0.3: render MEMORY.md / USER.md / SOUL.md as prompt sections."""
    if memory_dir is None:
        return ""
    from eaccode.memory.markdown_store import MarkdownMemoryStore
    from eaccode.memory.store import MemoryStore

    store = MarkdownMemoryStore(memory_dir)
    project_hash = MemoryStore.project_hash(workdir)
    sections: list[str] = []
    memory_text = store.read("memory", project_hash)
    if memory_text.strip():
        sections.append(f"# Project Memory\n{memory_text.strip()}")
    user_text = store.read("user")
    if user_text.strip():
        sections.append(f"# User Profile\n{user_text.strip()}")
    soul_text = store.read("soul")
    if soul_text.strip():
        sections.append(f"# Working Style\n{soul_text.strip()}")
    return "\n\n".join(sections)


def build_agent(
    workdir: Path,
    *,
    mode: PermissionMode | None = None,
    max_turns: int | None = None,
    allowed_tools: list[str] | None = None,
    model: str | None = None,
    settings: Settings | None = None,
    paths: EaccodePaths | None = None,
    client_cls: type[LLMClient] | None = None,
    mcp_tools: list | None = None,
) -> tuple[AgentLoop, LLMClient, SystemContext]:
    """Build a fully wired agent (sync — for `eaccode run` and CLI)."""
    import asyncio

    return asyncio.run(
        build_agent_async(
            workdir,
            mode=mode,
            max_turns=max_turns,
            allowed_tools=allowed_tools,
            model=model,
            settings=settings,
            paths=paths,
            client_cls=client_cls,
            mcp_tools=mcp_tools,
        )
    )


async def build_agent_async(
    workdir: Path,
    *,
    mode: PermissionMode | None = None,
    max_turns: int | None = None,
    allowed_tools: list[str] | None = None,
    model: str | None = None,
    settings: Settings | None = None,
    paths: EaccodePaths | None = None,
    client_cls: type[LLMClient] | None = None,
    mcp_tools: list | None = None,
) -> tuple[AgentLoop, LLMClient, SystemContext]:
    """Build a fully wired agent (async — for the Textual REPL)."""
    paths = paths or EaccodePaths()
    settings = settings or Settings.load(paths.settings_file)
    providers = load_providers(paths.providers_file)

    # Resolve at runtime so tests can monkeypatch eaccode.agent.factory.LLMClient
    client_cls = client_cls or LLMClient

    if model:
        from eaccode.llm.model_switch import ModelResolver

        resolved = ModelResolver().resolve(model)
        provider_name, default_model = resolved.provider, resolved.model
    elif providers:
        provider = next(
            (p for p in providers if p.name == settings.default_provider), providers[0]
        )
        provider_name, default_model = provider.name, provider.model
    else:
        raise RuntimeError(
            "No providers configured. Add one first:\n"
            "  eaccode providers add --provider minimax --model MiniMax-M3"
        )

    client = client_cls(
        default_model=default_model,
        providers_file=paths.providers_file,
        provider_name=provider_name,
        effort=settings.effort,
    )
    registry = build_default_registry(allowed_tools)
    for tool in mcp_tools or []:
        registry.register(tool)
    policy = PolicyEngine(mode=mode or settings.permission_mode, rules=RuleSet())

    memory = MemoryStore(paths.memory_dir)
    # P0.3: first-run setup of USER.md/SOUL.md (+ MEMORY.md dirs on demand).
    from eaccode.memory.markdown_store import MarkdownMemoryStore

    MarkdownMemoryStore(paths.memory_dir).ensure_first_run()
    sysctx = await build_system_context_async(
        workdir,
        skills_dirs=[
            paths.skills_dir,
            *[Path(d) for d in settings.skills.dirs],  # A.7: extra dirs
        ],
        memory=memory,
        ignore_rules=settings.ignore_rules,
        markdown_memory_dir=paths.memory_dir,
        skills_auto_load=settings.skills.auto_load,
    )
    agent = AgentLoop(
        client,
        registry,
        policy,
        AgentConfig(
            workdir=workdir,
            max_turns=max_turns or settings.max_turns,
            system_prompt=sysctx.system_prompt,
            # P0.2: auto-compaction settings (settings.yaml auto_compact /
            # compact_threshold). The loop compacts when the window fills.
            auto_compact=settings.auto_compact,
            compact_threshold=settings.compact_threshold,
            # P0.10: hooks (config_dir/hooks; disabled via settings).
            hooks_dir=paths.hooks_dir if settings.hooks_enabled else None,
        ),
    )
    for tool in registry.list():
        if tool.name == "delegate_task":
            tool.delegate_builder = build_agent_async
    return agent, client, sysctx
