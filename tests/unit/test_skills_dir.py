"""P7/A.4: build_agent_async must thread paths.skills_dir into AgentConfig."""

import asyncio
from pathlib import Path

import pytest


class _StubClient:
    def __init__(self, default_model, providers_file, provider_name,
                 effort=None, timeout=None):
        self.default_model = default_model
        self.provider_name = provider_name


@pytest.mark.asyncio
async def test_agent_config_has_skills_dir(tmp_path, monkeypatch):
    expected = tmp_path / "my_skills"
    (tmp_path / "providers.yaml").write_text(
        "- name: minimax\n  api_key: sk-test\n  model: MiniMax-M3\n",
        encoding="utf-8",
    )

    class _FakePaths:
        config_dir = tmp_path
        data_dir = tmp_path / "data"
        memory_dir = tmp_path / "memory"
        skills_dir = expected
        hooks_dir = tmp_path / "hooks"
        providers_file = tmp_path / "providers.yaml"
        settings_file = tmp_path / "settings.yaml"
        cron_db = tmp_path / "cron.db"
        sessions_dir = tmp_path / "sessions"
        plugins_dir = tmp_path / "plugins"

    from eaccode.agent import factory as factory_mod
    from eaccode.config import paths as paths_mod
    from eaccode.llm import client as llm_client

    monkeypatch.setattr(factory_mod, "EaccodePaths", _FakePaths)
    monkeypatch.setattr(paths_mod, "EaccodePaths", _FakePaths)
    monkeypatch.setattr(llm_client, "LLMClient", _StubClient)

    from eaccode.agent.factory import build_agent_async

    agent, *_ = await build_agent_async(workdir=tmp_path)
    assert Path(agent.config.skills_dir) == Path(expected)