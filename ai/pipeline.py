"""Investigation pipeline — Milestone 4 (real persistence).

    Raw Input
       ↓
    Preprocessing
       ↓
    Entity Extraction
       ↓
    Entity Resolution          (deterministic candidates only)
       ↓
    Relationship Extraction    (explicit rules / structured sources)
       ↓
    Validation
       ↓
    Persistence                (PostgreSQL canonical store; in-memory fallback)
       ↓
    Graph Synchronization      (Neo4j analytical projection; in-memory fallback)

Every stage is an independently callable method, so each can be tested
in isolation. The pipeline never mutates the canonical model and never
auto-merges ambiguous entities.

Persistence is injected via the PersistenceSink protocol. Production uses
ai.persistence.PostgresPersistence (PostgreSQL, idempotent upserts,
parameterized SQL, transaction-safe). Tests default to InMemoryPersistence
so no database is required for unit tests.

SAFETY: outputs describe entities/relationships/patterns only. No guilt,
criminality, or risk-verdict fields exist anywhere in this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .entity_resolution import (
    DeterministicEntityResolver,
    ResolutionCandidate,
)
from .extraction.base import EntityExtractor, ExtractedEntity
from .relationship_rules import RelationshipExtractor, RuleRelationship

_WHITESPACE_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Stage contracts
# ---------------------------------------------------------------------------

class PersistenceSink(Protocol):
    """Where validated entities/relationships are durably stored."""

    def save_entity(self, entity_id: str, entity_type: str,
                    payload: Dict[str, Any]) -> None: ...

    def save_relationship(self, relationship_id: str,
                          payload: Dict[str, Any]) -> None: ...


class InMemoryPersistence:
    """Simple dict-backed sink for tests and local development."""

    def __init__(self) -> None:
        self.entities: Dict[str, Dict[str, Any]] = {}
        self.relationships: Dict[str, Dict[str, Any]] = {}

    def save_entity(self, entity_id: str, entity_type: str,
                    payload: Dict[str, Any]) -> None:
        self.entities[entity_id] = {"entity_type": entity_type, **payload}

    def save_relationship(self, relationship_id: str,
                          payload: Dict[str, Any]) -> None:
        self.relationships[relationship_id] = payload


class GraphRepositoryProtocol(Protocol):
    """Structural subset of the graph repository the pipeline needs.

    Full interface lives in ``app.graph.base`` (backend-python).
    """

    def upsert_entity(self, entity_id: str, entity_type: str,
                      properties: Dict[str, Any]) -> None: ...

    def upsert_relationship(self, relationship_id: str, source_id: str,
                            source_type: str, target_id: str,
                            target_type: str, relationship_type: str,
                            properties: Dict[str, Any]) -> None: ...


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    source_id: Optional[str]
    preprocessed_text: str = ""
    entities: List[ExtractedEntity] = field(default_factory=list)
    resolutions: Dict[str, List[ResolutionCandidate]] = field(
        default_factory=dict)
    relationships: List[RuleRelationship] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    persisted_entities: int = 0
    persisted_relationships: int = 0
    graph_nodes_upserted: int = 0
    graph_relationships_upserted: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "preprocessed_text": self.preprocessed_text,
            "entities": [e.to_dict() for e in self.entities],
            "resolutions": {
                key: [c.to_dict() for c in cands]
                for key, cands in self.resolutions.items()
            },
            "relationships": [r.to_dict() for r in self.relationships],
            "validation_errors": list(self.validation_errors),
            "persisted": {
                "entities": self.persisted_entities,
                "relationships": self.persisted_relationships,
            },
            "graph_sync": {
                "nodes": self.graph_nodes_upserted,
                "relationships": self.graph_relationships_upserted,
            },
        }


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class InvestigationPipeline:
    """Composable investigation pipeline with independent stages."""

    def __init__(
        self,
        extractor: EntityExtractor,
        resolver: DeterministicEntityResolver,
        relationship_extractor: RelationshipExtractor,
        persistence: Optional[PersistenceSink] = None,
        graph_repository: Optional[GraphRepositoryProtocol] = None,
    ):
        self.extractor = extractor
        self.resolver = resolver
        self.relationship_extractor = relationship_extractor
        self.persistence = persistence
        self.graph_repository = graph_repository

    # -- stage 1: preprocessing -------------------------------------------

    @staticmethod
    def preprocess(raw_text: str) -> str:
        """Normalize whitespace; keep offsets stable otherwise."""
        if not isinstance(raw_text, str):
            raise ValueError("raw input must be a string")
        text = raw_text.replace("\r\n", "\n")
        text = _WHITESPACE_RE.sub(" ", text)
        return text.strip()

    # -- stage 2: entity extraction ----------------------------------------

    def extract_entities(self, text: str, source_id: Optional[str] = None
                         ) -> List[ExtractedEntity]:
        return self.extractor.extract(text, source_id=source_id)

    # -- stage 3: entity resolution -----------------------------------------

    def resolve_entities(
        self, entities: List[ExtractedEntity]
    ) -> Dict[str, List[ResolutionCandidate]]:
        resolutions: Dict[str, List[ResolutionCandidate]] = {}
        for ent in entities:
            if ent.entity_id is not None:
                continue  # already linked to a canonical entity
            candidates = self.resolver.resolve(
                ent.normalized_value or ent.text, ent.entity_type)
            if candidates:
                resolutions[self._mention_key(ent)] = candidates
        return resolutions

    # -- stage 4: relationship extraction ------------------------------------

    def extract_relationships(
        self,
        entities: List[ExtractedEntity],
        text: str,
        source_id: Optional[str] = None,
        structured_records: Optional[List[Dict[str, Any]]] = None,
    ) -> List[RuleRelationship]:
        # Attach resolved entity_ids to mentions before rule application.
        for ent in entities:
            if ent.entity_id is None:
                candidates = self.resolutions_for(ent) if hasattr(
                    self, "_last_resolutions") else []
                auto = [c for c in candidates if c.status == "auto_linked"]
                if len(auto) == 1:
                    ent.entity_id = auto[0].candidate_entity_id
        return self.relationship_extractor.extract_relationships(
            entities, text, source_id=source_id,
            structured_records=structured_records)

    def resolutions_for(self, ent: ExtractedEntity) -> List[ResolutionCandidate]:
        return getattr(self, "_last_resolutions", {}).get(
            self._mention_key(ent), [])

    # -- stage 5: validation ---------------------------------------------------

    def validate(self, result: PipelineResult) -> List[str]:
        errors: List[str] = []
        for ent in result.entities:
            try:
                ent.validate()
            except Exception as exc:  # ExtractionError
                errors.append(f"entity invalid: {exc}")
        seen_rel_ids = set()
        for rel in result.relationships:
            if not 0.0 <= rel.confidence <= 1.0:
                errors.append(
                    f"{rel.relationship_id}: confidence outside [0,1]")
            if rel.source_entity_id == rel.target_entity_id and \
                    rel.source_type == rel.target_type and \
                    rel.source_entity_id is not None:
                errors.append(f"{rel.relationship_id}: self-loop forbidden")
            if rel.source_type == rel.target_type == "Person" and \
                    rel.relationship_type != "KNOWS":
                errors.append(
                    f"{rel.relationship_id}: person-person must be KNOWS")
            if rel.relationship_id in seen_rel_ids:
                errors.append(f"duplicate relationship_id "
                              f"{rel.relationship_id}")
            seen_rel_ids.add(rel.relationship_id)
            for side in ("source", "target"):
                if getattr(rel, f"{side}_entity_id") is None:
                    errors.append(
                        f"{rel.relationship_id}: unresolved {side} mention "
                        "'{}' requires review before persistence".format(
                            getattr(rel, f"{side}_text")))
        result.validation_errors = errors
        return errors

    # -- stages 6 & 7: persistence + graph sync ---------------------------------

    def persist(self, result: PipelineResult) -> None:
        if self.persistence is None:
            raise RuntimeError("no persistence sink configured")
        if result.validation_errors:
            raise ValueError(
                "refusing to persist data with validation errors: "
                f"{result.validation_errors}")
        for ent in result.entities:
            if ent.entity_id is None:
                continue
            self.persistence.save_entity(
                ent.entity_id, ent.entity_type,
                {"text": ent.text,
                 "normalized_value": ent.normalized_value,
                 "source_id": ent.source_id})
            result.persisted_entities += 1
        for rel in result.relationships:
            if rel.source_entity_id is None or rel.target_entity_id is None:
                continue
            self.persistence.save_relationship(
                rel.relationship_id, rel.to_dict())
            result.persisted_relationships += 1

    def sync_graph(self, result: PipelineResult) -> None:
        if self.graph_repository is None:
            raise RuntimeError("no graph repository configured")
        if result.validation_errors:
            raise ValueError(
                "refusing to synchronize data with validation errors: "
                f"{result.validation_errors}")
        for ent in result.entities:
            if ent.entity_id is None:
                continue
            self.graph_repository.upsert_entity(
                ent.entity_id, ent.entity_type,
                {"text": ent.text,
                 "normalized_value": ent.normalized_value})
            result.graph_nodes_upserted += 1
        for rel in result.relationships:
            if rel.source_entity_id is None or rel.target_entity_id is None:
                continue
            self.graph_repository.upsert_relationship(
                rel.relationship_id,
                rel.source_entity_id, rel.source_type,
                rel.target_entity_id, rel.target_type,
                rel.relationship_type,
                {"confidence": rel.confidence,
                 "extraction_method": rel.extraction_method,
                 "timestamp": rel.timestamp})
            result.graph_relationships_upserted += 1

    # -- orchestration ------------------------------------------------------------

    def run(self, raw_text: str, source_id: Optional[str] = None,
            structured_records: Optional[List[Dict[str, Any]]] = None,
            do_persist: bool = True, do_sync: bool = True) -> PipelineResult:
        result = PipelineResult(source_id=source_id)
        result.preprocessed_text = self.preprocess(raw_text)
        result.entities = self.extract_entities(
            result.preprocessed_text, source_id=source_id)
        self._last_resolutions = self.resolve_entities(result.entities)
        result.resolutions = self._last_resolutions
        result.relationships = self.extract_relationships(
            result.entities, result.preprocessed_text,
            source_id=source_id, structured_records=structured_records)
        self.validate(result)

        # Only persist/sync if the corresponding sink is configured
        if do_persist and not result.validation_errors and self.persistence is not None:
            self.persist(result)
        if do_sync and not result.validation_errors and self.graph_repository is not None:
            self.sync_graph(result)
        return result

    @staticmethod
    def _mention_key(ent: ExtractedEntity) -> str:
        return f"{ent.start_offset}:{ent.end_offset}:{ent.text}"
