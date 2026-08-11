"""Learning graph (C.7) — skills + memory facts as a knowledge graph.

Nodes are skills and facts; an edge connects a skill to a fact when the
fact text appears in the skill's content. ``density`` measures how
interconnected the graph is; ``recency_ink`` decays a timestamp towards
0 so stale nodes visibly fade (Hermes' recency rendering idea).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

HALF_LIFE_DAYS = 30.0


@dataclass
class Node:
    id: str
    kind: str  # skill | fact
    name: str
    last_used: datetime | None = None
    weight: int = 0  # use count


@dataclass
class Graph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)  # (skill_id, fact_id)

    def density(self) -> float:
        """Edge count over the maximum possible edges (0 when < 2 nodes)."""
        n = len(self.nodes)
        if n < 2:
            return 0.0
        return len(self.edges) / (n * (n - 1) / 2)

    def delete_node(self, node_id: str) -> bool:
        """Remove a node and its edges; True when it existed."""
        before = len(self.nodes)
        self.nodes = [n for n in self.nodes if n.id != node_id]
        self.edges = [
            (a, b) for a, b in self.edges if a != node_id and b != node_id
        ]
        return len(self.nodes) < before


def recency_ink(ts: datetime | None, now: datetime | None = None,
                half_life_days: float = HALF_LIFE_DAYS) -> float:
    """0..1 recency: 1 = now, 0.5 after one half-life, → 0 for old."""
    if ts is None:
        return 0.0
    now = now or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
    return math.exp(-math.log(2) * age_days / half_life_days)


def build_graph(skills: list[Any], facts: list[str]) -> Graph:
    """Skill nodes + fact nodes; edges when a fact appears in the skill."""
    graph = Graph()
    for s in skills:
        graph.nodes.append(
            Node(id=f"skill:{s.name}", kind="skill", name=s.name,
                 last_used=s.last_used,
                 weight=getattr(s, "weight", 0))
        )
    for i, fact in enumerate(facts):
        graph.nodes.append(
            Node(id=f"fact:{i}", kind="fact", name=fact)
        )
    for s in skills:
        for i, fact in enumerate(facts):
            if fact.lower() in (s.content or "").lower():
                graph.edges.append((f"skill:{s.name}", f"fact:{i}"))
    return graph
