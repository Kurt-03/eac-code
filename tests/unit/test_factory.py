"""Tests for the agent factory (system prompt wiring: context+memory+skills)."""

from eaccode.agent.factory import build_system_context


def test_build_system_context_wires_everything(tmp_path, monkeypatch):
    # project rules file
    (tmp_path / ".git").mkdir()
    (tmp_path / "EACCODE.md").write_text("# Rules\nUse 2-space indent")
    # a skill
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "git.md").write_text(
        "---\nname: git\ndescription: git workflow\n---\nAlways git status first"
    )
    # memory facts
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    from eaccode.memory.store import MemoryStore

    store = MemoryStore(memory_dir)
    import asyncio

    asyncio.run(store.remember(MemoryStore.project_hash(tmp_path), "Build nutzt uv"))

    ctx = build_system_context(
        workdir=tmp_path,
        skills_dirs=[skills_dir],
        memory=store,
    )
    assert "Use 2-space indent" in ctx.system_prompt  # Projekt-Regeln
    assert "Build nutzt uv" in ctx.system_prompt  # Auto-Memory
    assert "[memory]" in ctx.system_prompt
    assert "git status first" in ctx.system_prompt  # Skills
    assert "Self-improvement" in ctx.system_prompt
    assert ctx.memory_facts == ["Build nutzt uv"]
