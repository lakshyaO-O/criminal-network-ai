"""In-memory persistence — test and development fallback (Milestone 3 compatibility).

Implements the same contract as PostgresPersistence but keeps all data in
dicts. No external services required. Used by unit tests and when
DATABASE_URL is not configured.

The class also satisfies the legacy ai.pipeline.PersistenceSink protocol
(save_entity/save_relationship) so existing pipelines continue to work.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, List, Optional


class InMemoryPersistence:
    """Dict-backed persistence. Mirrors PostgresPersistence semantics.

    - save_entity/save_relationship are idempotent (upsert)
    - get_entity searches across all stored entities by ID
    - get_relationships scans the relationships dict
    - transaction() is a no-op context manager (in-memory is atomic)
    """

    def __init__(self) -> None:
        self.entities: Dict[str, Dict[str, Any]] = {}
        self.relationships: Dict[str, Dict[str, Any]] = {}
        self.cases: Dict[str, Dict[str, Any]] = {}
        self.evidence: Dict[str, Dict[str, Any]] = {}
        # Keep per-entity-type counts for health parity
        self._entity_type_counts: Dict[str, int] = {}

    # -- writes -------------------------------------------------------------

    def save_entity(self, entity_id: str, entity_type: str, payload: Dict[str, Any]) -> str:
        existed = entity_id in self.entities
        # Preserve canonical fields; merge payload
        # Ensure deterministic chain_hash for Evidence
        if entity_type == "Evidence" and not payload.get("chain_hash"):
            try:
                from blockchain.evidence_chain import compute_evidence_chain_hash
                prev = "0"
                if self.evidence:
                    last = list(self.evidence.values())[-1]
                    if last.get("chain_hash"):
                        prev = last["chain_hash"]
                payload = dict(payload)
                payload["chain_hash"] = compute_evidence_chain_hash(entity_id, payload, prev)
            except Exception:
                pass
        self.entities[entity_id] = {"entity_id": entity_id, "entity_type": entity_type, **payload}
        # Also index by type for get_case/get_evidence helpers when appropriate
        if entity_type == "Case":
            self.cases[entity_id] = self.entities[entity_id]
        elif entity_type == "Evidence":
            self.evidence[entity_id] = self.entities[entity_id]
        return "updated" if existed else "inserted"

    def save_relationship(self, relationship_id: str, payload: Dict[str, Any]) -> str:
        existed = relationship_id in self.relationships
        self.relationships[relationship_id] = {"relationship_id": relationship_id, **payload}
        return "updated" if existed else "inserted"

    def save_case(self, case_id: str, payload: Dict[str, Any]) -> str:
        return self.save_entity(case_id, "Case", payload)

    def save_evidence(self, evidence_id: str, payload: Dict[str, Any]) -> str:
        # Deterministic chain_hash mirroring Postgres behavior
        if not payload.get("chain_hash"):
            try:
                from blockchain.evidence_chain import compute_evidence_chain_hash
                prev = "0"
                # Use last evidence chain_hash if present for linkage
                if self.evidence:
                    last = list(self.evidence.values())[-1]
                    if last.get("chain_hash"):
                        prev = last["chain_hash"]
                payload = dict(payload)
                payload["chain_hash"] = compute_evidence_chain_hash(evidence_id, payload, prev)
            except Exception:
                pass
        return self.save_entity(evidence_id, "Evidence", payload)

    # -- reads --------------------------------------------------------------

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        return self.entities.get(entity_id)

    def get_relationships(self, entity_id: str) -> List[Dict[str, Any]]:
        return [
            rel for rel in self.relationships.values()
            if rel.get("source", {}).get("entity_id") == entity_id
            or rel.get("source_id") == entity_id
            or rel.get("target", {}).get("entity_id") == entity_id
            or rel.get("target_id") == entity_id
        ]

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        # Prefer indexed cases, fallback to generic entities
        return self.cases.get(case_id) or self.entities.get(case_id)

    def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        return self.evidence.get(evidence_id) or self.entities.get(evidence_id)

    def health_check(self) -> bool:
        return True

    @contextmanager
    def transaction(self):
        # In-memory is atomic; just yield. On exception, no partial commit concept,
        # but we snapshot to allow rollback for test parity.
        snapshot_entities = dict(self.entities)
        snapshot_rels = dict(self.relationships)
        try:
            yield self
        except Exception:
            self.entities = snapshot_entities
            self.relationships = snapshot_rels
            raise

    # -- helpers for pipeline compatibility ---------------------------------

    def count_entities(self) -> int:
        return len(self.entities)

    def count_relationships(self) -> int:
        return len(self.relationships)
