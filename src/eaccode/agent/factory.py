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
    """Compose the system prompt from project rules + memory + skills."""
    project_rules = "" if ignore_rules else discover_project_context(workdir)
    memory_facts: list[str] = []
    if memory is not None and not ignore_rules:
        memory_facts = _recall_sync(memory, workdir)
    skills = ""
    if skills_dirs and not ignore_rules:
        skills = skills_to_system_prompt_section(discover_skills(skills_dirs))
    prompt = build_system_prompt(
        project_rules=project_rules,
        memory_facts=memory_facts,
        skills=skills,
        workdir=str(workdir),
    )
    return SystemContext(system_prompt=prompt, memory_facts=memory_facts)


def _recall_sync(memory: MemoryStore, workdir: Path) -> list[str]:
    import asyncio

    return asyncio.run(memory.recall(MemoryStore.project_hash(workdir)))


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
) -> tuple[AgentLoop, LLMClient, SystemContext]:
    """Build a fully wired agent (used by `eaccode run` and the REPL)."""
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
    policy = PolicyEngine(mode=mode or settings.permission_mode, rules=RuleSet())

    memory = MemoryStore(paths.memory_dir)
    sysctx = build_system_context(
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
    return agent, client, sysctx
