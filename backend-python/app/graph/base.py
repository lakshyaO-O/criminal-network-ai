"""Graph repository abstraction.

Application code depends on :class:`GraphRepository` only — never on
Neo4j query syntax. Implementations:

- ``app.graph.memory.InMemoryGraphRepository``  (tests, local dev, no Docker)
- ``app.graph.neo4j_repo.Neo4jGraphRepository`` (lazy driver import)

Supported operations (Milestone 3 scope):
- entity upsert / lookup
- relationship upsert / lookup
- neighborhood traversal
- shortest path
- graph statistics

Advanced analytics are intentionally out of scope here; the analysis
service works on the repository's exported snapshot instead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class GraphRepositoryError(RuntimeError):
    pass


@dataclass
class GraphStats:
    node_count: int
    relationship_count: int
    type_counts: Dict[str, int] = field(default_factory=dict)
    relationship_type_counts: Dict[str, int] = field(default_factory=dict)
    avg_degree: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_count": self.node_count,
            "relationship_count": self.relationship_count,
            "type_counts": self.type_counts,
            "relationship_type_counts": self.relationship_type_counts,
            "avg_degree": self.avg_degree,
        }


class GraphRepository(ABC):
    """Storage-neutral graph interface."""

    @abstractmethod
    def upsert_entity(self, entity_id: str, entity_type: str,
                      properties: Dict[str, Any]) -> None: ...

    @abstractmethod
    def upsert_relationship(self, relationship_id: str, source_id: str,
                            source_type: str, target_id: str,
                            target_type: str, relationship_type: str,
                            properties: Dict[str, Any]) -> None: ...

    @abstractmethod
    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def get_relationships(self, entity_id: str) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def neighborhood(self, entity_id: str, depth: int = 1
                     ) -> Dict[str, Any]: ...

    @abstractmethod
    def shortest_path(self, from_entity_id: str, to_entity_id: str,
                      max_depth: int = 6) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def statistics(self) -> GraphStats: ...

    # Shared helpers ------------------------------------------------------

    def _snapshot(self) -> Tuple[Dict[str, Tuple[str, Dict[str, Any]]],
                                 List[Dict[str, Any]]]:
        """Default adjacency-based implementations build on this."""
        raise NotImplementedError


def bfs_neighborhood(adjacency: Dict[str, List[Tuple[str, str]]],
                     start: str, depth: int) -> Dict[str, Any]:
    """Shared BFS used by both implementations.

    adjacency: entity_id -> list of (neighbor_id, via_relationship_type)
    """
    visited = {start}
    frontier = {start}
    nodes: List[Dict[str, Any]] = [{"entity_id": start, "depth": 0}]
    edges: List[Dict[str, Any]] = []
    for current_depth in range(1, depth + 1):
        next_frontier: set = set()
        for node in frontier:
            for neighbor, rel_type in adjacency.get(node, ()):
                edges.append({"from": node, "to": neighbor,
                              "relationship_type": rel_type})
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
                    nodes.append({"entity_id": neighbor,
                                  "depth": current_depth})
        frontier = next_frontier
        if not frontier:
            break
    return {"start_entity_id": start, "depth": depth,
            "nodes": nodes, "edges": edges}


def bfs_shortest_path(adjacency: Dict[str, List[Tuple[str, str]]],
                      src: str, dst: str,
                      max_depth: int) -> Optional[Dict[str, Any]]:
    if src == dst:
        return {"found": True, "length": 0,
                "entities": [src], "relationships": []}
    queue: deque = deque([(src, [src], [])])
    while queue:
        node, path, rels = queue.popleft()
        if len(path) - 1 >= max_depth:
            continue
        for neighbor, rel_type in adjacency.get(node, ()):
            if neighbor in path:  # simple paths only
                continue
            new_path, new_rels = path + [neighbor], rels + [rel_type]
            if neighbor == dst:
                return {"found": True, "length": len(new_path) - 1,
                        "entities": new_path, "relationships": new_rels}
            queue.append((neighbor, new_path, new_rels))
    return {"found": False, "length": None, "entities": [],
            "relationships": []}
