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
) -> SystemContext:
    """Compose the system prompt (sync — for CLI contexts without a loop)."""
    import asyncio

    return asyncio.run(
        build_system_context_async(
            workdir,
            skills_dirs=skills_dirs,
            memory=memory,
            ignore_rules=ignore_rules,
        )
    )


async def build_system_context_async(
    workdir: Path,
    *,
    skills_dirs: list[Path] | None = None,
    memory: MemoryStore | None = None,
    ignore_rules: bool = False,
) -> SystemContext:
    """Compose the system prompt from project rules + memory + skills.

    Async variant — the REPL runs inside Textual's event loop, where
    asyncio.run() is forbidden ("cannot be called from a running event loop").
    """
    project_rules = "" if ignore_rules else discover_project_context(workdir)
    memory_facts: list[str] = []
    if memory is not None and not ignore_rules:
        memory_facts = await memory.recall(MemoryStore.project_hash(workdir))
    skills = ""
    if skills_dirs and not ignore_rules:
        skills = skills_to_system_prompt_section(discover_skills(skills_dirs))
    key = (
        str(workdir), project_rules, tuple(memory_facts), skills, ignore_rules,
    )
    cached = _prompt_cache.get(key)
    if cached is not None:
        return cached
    prompt = build_system_prompt(
        project_rules=project_rules,
        memory_facts=memory_facts,
        skills=skills,
        workdir=str(workdir),
    )
    ctx = SystemContext(system_prompt=prompt, memory_facts=memory_facts)
    if len(_prompt_cache) >= _PROMPT_CACHE_MAX:
        _prompt_cache.clear()
    _prompt_cache[key] = ctx
    return ctx


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
    sysctx = await build_system_context_async(
        workdir,
        skills_dirs=[paths.skills_dir],
        memory=memory,
        ignore_rules=settings.ignore_rules,
    )
    agent = AgentLoop(
        client,
        registry,
        policy,
        AgentConfig(
            workdir=workdir,
            max_turns=max_turns or settings.max_turns,
            system_prompt=sysctx.system_prompt,
        ),
    )
    # expose the agent builder to delegate_task (Phase C.3)
    for tool in registry.list():
        if tool.name == "delegate_task":
            tool.delegate_builder = build_agent_async
    return agent, client, sysctx
