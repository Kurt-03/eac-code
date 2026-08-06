"""Tests for the auto-memory store (Task 6.3)."""
import pytest

from eaccode.memory.store import MemoryStore


@pytest.mark.asyncio
async def test_remember_and_recall(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    await store.remember("projekt-hash-1", "Der Build nutzt uv statt pip")
    await store.remember("projekt-hash-1", "Tests laufen mit pytest -x")
    facts = await store.recall("projekt-hash-1")
    assert len(facts) == 2
    assert "uv" in facts[0]


@pytest.mark.asyncio
async def test_memory_is_per_project(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    await store.remember("projekt-a", "Fakt über A")
    assert await store.recall("projekt-b") == []


@pytest.mark.asyncio
async def test_forget(tmp_path):
    store = MemoryStore(tmp_path / "memory")
    await store.remember("p1", "temporärer Fakt")
    await store.forget("p1", "temporärer Fakt")
    assert await store.recall("p1") == []


@pytest.mark.asyncio
async def test_cap_memory_per_project(tmp_path):
    store = MemoryStore(tmp_path / "memory", max_entries=3)
    for i in range(5):
        await store.remember("p1", f"Fakt {i}")
    facts = await store.recall("p1")
    assert len(facts) == 3  # älteste fliegen raus (FIFO-Cap)


def test_project_hash_is_stable(tmp_path):
    h1 = MemoryStore.project_hash(tmp_path)
    h2 = MemoryStore.project_hash(tmp_path)
    assert h1 == h2
    assert len(h1) == 16
