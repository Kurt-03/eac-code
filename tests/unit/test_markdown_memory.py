"""Tests for the markdown memory store + tools (P0.3)."""

import pytest

from eaccode.memory.markdown_store import (
    MEMORY_BUDGET,
    SOUL_BUDGET,
    USER_BUDGET,
    BudgetExceededError,
    MarkdownMemoryStore,
)
from eaccode.tools.base import ToolContext


@pytest.fixture
def store(tmp_path):
    return MarkdownMemoryStore(tmp_path)


class TestStore:
    def test_read_missing_returns_empty(self, store):
        assert store.read("memory", "h1") == ""
        assert store.read("user") == ""

    def test_write_and_read_roundtrip(self, store):
        store.write("user", "# User Profile\n\n- John\n")
        assert store.read("user") == "# User Profile\n\n- John\n"

    def test_memory_is_project_scoped(self, store):
        store.write("memory", "project A fact", "hash-a")
        assert store.read("memory", "hash-b") == ""
        assert store.read("memory", "hash-a") == "project A fact"

    def test_budget_enforced(self, store):
        with pytest.raises(BudgetExceededError):
            store.write("soul", "x" * (SOUL_BUDGET + 1))
        # At exactly the budget it fits.
        store.write("soul", "x" * SOUL_BUDGET)
        assert len(store.read("soul")) == SOUL_BUDGET

    def test_add_fact_dedupes_and_lists(self, store):
        store.add_fact("memory", "build uses uv", "h1")
        store.add_fact("memory", "build uses uv", "h1")  # dedupe
        store.add_fact("memory", "tests: pytest", "h1")
        text = store.read("memory", "h1")
        assert text.count("build uses uv") == 1
        assert "- tests: pytest" in text

    def test_remove_line(self, store):
        store.add_fact("memory", "alpha", "h1")
        store.add_fact("memory", "beta", "h1")
        assert store.remove_line("memory", "alpha", "h1") is True
        assert store.remove_line("memory", "nope", "h1") is False
        assert "alpha" not in store.read("memory", "h1")
        assert "beta" in store.read("memory", "h1")

    def test_replace_fact(self, store):
        store.add_fact("memory", "old fact", "h1")
        assert store.replace_fact("memory", "old fact", "new fact", "h1") is True
        assert "new fact" in store.read("memory", "h1")
        assert "old fact" not in store.read("memory", "h1")

    def test_ensure_first_run_creates_global_files(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        store.ensure_first_run()
        assert (tmp_path / "USER.md").exists()
        assert (tmp_path / "SOUL.md").exists()
        # Idempotent.
        store.ensure_first_run()

    def test_first_run_soul_has_template(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        store.ensure_first_run()
        soul = store.read("soul")
        assert "Working Style" in soul
        assert "direct and honest" in soul  # A.8 template body

    def test_trim_drops_oldest_facts_until_budget(self, tmp_path):
        # The file is over budget because it was edited externally —
        # the budget guard only applies to store writes.
        store = MarkdownMemoryStore(tmp_path)
        store.add_fact("memory", "old fact 1", "h1")
        store.add_fact("memory", "old fact 2", "h1")
        path = store._path("memory", "h1")
        path.write_text(
            path.read_text(encoding="utf-8") + "- " + "x" * (MEMORY_BUDGET + 200),
            encoding="utf-8",
        )
        removed = store.trim("memory", "h1")
        assert removed >= 2
        text = store.read("memory", "h1")
        assert len(text) <= MEMORY_BUDGET
        assert "old fact 1" not in text  # oldest went first

    def test_trim_protects_headers(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        store.write("user", "# User Profile\n\n- " + "y" * (USER_BUDGET + 100))
        removed = store.trim("user")
        assert removed >= 1
        assert store.read("user").startswith("# User Profile")

    def test_trim_within_budget_is_noop(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        store.add_fact("memory", "small", "h1")
        assert store.trim("memory", "h1") == 0


class TestTools:
    @pytest.fixture
    def ctx(self, tmp_path):
        return ToolContext(workdir=tmp_path, memory_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_remember_recall_roundtrip(self, ctx):
        from eaccode.memory.memory_tools import (
            MemoryRecallInput,
            MemoryRecallTool,
            MemoryRememberInput,
            MemoryRememberTool,
        )

        tool = MemoryRememberTool()
        assert tool.requires_permission is True
        result = await tool.run(MemoryRememberInput(fact="use uv"), ctx)
        assert result.is_error is False

        recall = MemoryRecallTool()
        assert recall.requires_permission is False
        result = await recall.run(MemoryRecallInput(scope="memory"), ctx)
        assert "use uv" in result.content

    @pytest.mark.asyncio
    async def test_budget_error_surfaces_in_tool(self, ctx):
        from eaccode.memory.memory_tools import (
            MemoryRememberInput,
            MemoryRememberTool,
        )

        result = await MemoryRememberTool().run(
            MemoryRememberInput(fact="x" * (MEMORY_BUDGET + 50)), ctx
        )
        assert result.is_error is True
        assert "budget" in result.content.lower()

    @pytest.mark.asyncio
    async def test_forget_and_edit(self, ctx):
        from eaccode.memory.memory_tools import (
            MemoryEditInput,
            MemoryEditTool,
            MemoryForgetInput,
            MemoryForgetTool,
            MemoryRememberInput,
            MemoryRememberTool,
        )

        await MemoryRememberTool().run(
            MemoryRememberInput(fact="lesson: check tests"), ctx
        )
        edit = await MemoryEditTool().run(
            MemoryEditInput(old="check tests", new="always run tests"), ctx
        )
        assert edit.is_error is False
        forget = await MemoryForgetTool().run(
            MemoryForgetInput(needle="always run tests"), ctx
        )
        assert forget.is_error is False

    @pytest.mark.asyncio
    async def test_recall_invalid_scope(self, ctx):
        from eaccode.memory.memory_tools import (
            MemoryRecallInput,
            MemoryRecallTool,
        )

        result = await MemoryRecallTool().run(MemoryRecallInput(scope="nope"), ctx)
        assert result.is_error is True


class TestPromptInjection:
    def test_markdown_sections_in_system_prompt(self, tmp_path):
        from eaccode.agent.factory import _markdown_memory_section
        from eaccode.memory.store import MemoryStore

        store = MarkdownMemoryStore(tmp_path)
        hash_ = MemoryStore.project_hash(tmp_path)
        store.write("memory", "- use uv", hash_)
        store.write("user", "- John")
        section = _markdown_memory_section(tmp_path, tmp_path)
        assert "Project Memory" in section
        assert "use uv" in section
        assert "User Profile" in section

    def test_empty_memory_yields_empty_section(self, tmp_path):
        from eaccode.agent.factory import _markdown_memory_section

        assert _markdown_memory_section(tmp_path, tmp_path) == ""
        assert _markdown_memory_section(tmp_path, None) == ""

    def test_tools_registered_in_registry(self):
        from eaccode.tools.factory import build_default_registry

        names = {t.name for t in build_default_registry().list()}
        assert {"memory_remember", "memory_recall", "memory_forget",
                "memory_edit"} <= names
