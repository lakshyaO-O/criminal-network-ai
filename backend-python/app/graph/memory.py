"""In-memory graph repository — used for tests and Docker-less dev."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .base import (
    GraphRepository,
    GraphRepositoryError,
    GraphStats,
    bfs_neighborhood,
    bfs_shortest_path,
)


class InMemoryGraphRepository(GraphRepository):
    def __init__(self) -> None:
        self._entities: Dict[str, Dict[str, Any]] = {}
        self._relationships: Dict[str, Dict[str, Any]] = {}

    # -- writes ------------------------------------------------------------

    def upsert_entity(self, entity_id: str, entity_type: str,
                      properties: Dict[str, Any]) -> None:
        self._entities[entity_id] = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            **properties,
        }

    def upsert_relationship(self, relationship_id: str, source_id: str,
                            source_type: str, target_id: str,
                            target_type: str, relationship_type: str,
                            properties: Dict[str, Any]) -> None:
        if source_id not in self._entities or target_id not in self._entities:
            raise GraphRepositoryError(
                f"cannot upsert {relationship_id}: endpoint(s) missing; "
                "upsert entities first")
        if source_id == target_id and source_type == target_type:
            raise GraphRepositoryError("self-loop relationships are forbidden")
        self._relationships[relationship_id] = {
            "relationship_id": relationship_id,
            "source_id": source_id, "source_type": source_type,
            "target_id": target_id, "target_type": target_type,
            "relationship_type": relationship_type,
            **properties,
        }

    # -- reads ---------------------------------------------------------------

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        return self._entities.get(entity_id)

    def get_relationships(self, entity_id: str) -> List[Dict[str, Any]]:
        return [
            rel for rel in self._relationships.values()
            if rel["source_id"] == entity_id or rel["target_id"] == entity_id
        ]

    def _adjacency(self) -> Dict[str, List[Tuple[str, str]]]:
        adj: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for rel in self._relationships.values():
            adj[rel["source_id"]].append(
                (rel["target_id"], rel["relationship_type"]))
            adj[rel["target_id"]].append(
                (rel["source_id"], rel["relationship_type"]))
        return adj

    def neighborhood(self, entity_id: str, depth: int = 1) -> Dict[str, Any]:
        if entity_id not in self._entities:
            raise GraphRepositoryError(f"unknown entity '{entity_id}'")
        return bfs_neighborhood(self._adjacency(), entity_id, depth)

    def shortest_path(self, from_entity_id: str, to_entity_id: str,
                      max_depth: int = 6) -> Optional[Dict[str, Any]]:
        for eid in (from_entity_id, to_entity_id):
            if eid not in self._entities:
                raise GraphRepositoryError(f"unknown entity '{eid}'")
        return bfs_shortest_path(self._adjacency(),
                                 from_entity_id, to_entity_id, max_depth)

    def statistics(self) -> GraphStats:
        type_counts: Dict[str, int] = defaultdict(int)
        for ent in self._entities.values():
            type_counts[ent["entity_type"]] += 1
        rel_type_counts: Dict[str, int] = defaultdict(int)
        for rel in self._relationships.values():
            rel_type_counts[rel["relationship_type"]] += 1
        n = len(self._entities)
        avg_degree = (2 * len(self._relationships) / n) if n else 0.0
        return GraphStats(
            node_count=n,
            relationship_count=len(self._relationships),
            type_counts=dict(type_counts),
            relationship_type_counts=dict(rel_type_counts),
            avg_degree=round(avg_degree, 4),
        )

    # -- export for the analysis service ---------------------------------------

    def export_snapshot(self) -> Tuple[Dict[str, Tuple[str, Dict[str, Any]]],
                                       List[Dict[str, Any]]]:
        return ({k: (v["entity_type"], v) for k, v in self._entities.items()},
                list(self._relationships.values()))
