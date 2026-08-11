"""Tests for the learning graph (C.7)."""

from datetime import UTC, datetime, timedelta

from eaccode.curator.learning_graph import build_graph, recency_ink
from eaccode.memory.skills import Skill


def _skill(name: str, content: str, days_old: float = 1) -> Skill:
    return Skill(
        name=name, description="d", content=content,
        source=None,
        last_used=datetime.now(UTC) - timedelta(days=days_old),
    )


def test_graph_nodes_and_edges():
    skills = [_skill("git", "always run git status"), _skill("tdd", "write tests")]
    facts = ["git status", "use pytest"]
    graph = build_graph(skills, facts)
    kinds = {n.kind for n in graph.nodes}
    assert kinds == {"skill", "fact"}
    assert ("skill:git", "fact:0") in graph.edges  # fact appears in content
    assert ("skill:tdd", "fact:0") not in graph.edges


def test_graph_density():
    graph = build_graph([], [])
    assert graph.density() == 0.0
    skills = [_skill("a", "fact1"), _skill("b", "fact2")]
    facts = ["fact1", "fact2"]
    graph = build_graph(skills, facts)
    assert graph.density() == 2 / 6  # 2 edges / C(4,2)


def test_delete_node_removes_edges():
    skills = [_skill("git", "git status"), _skill("other", "nothing")]
    graph = build_graph(skills, ["git status"])
    assert graph.delete_node("skill:git") is True
    assert graph.delete_node("skill:git") is False
    assert all(a != "skill:git" for a, _ in graph.edges)


def test_recency_ink_decay():
    now = datetime.now(UTC)
    assert recency_ink(now, now=now) == 1.0
    half = now - timedelta(days=30)
    assert abs(recency_ink(half, now=now) - 0.5) < 0.01
    old = now - timedelta(days=300)
    assert recency_ink(old, now=now) < 0.01
    assert recency_ink(None) == 0.0
