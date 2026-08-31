"""Common schemas for AI/ML entity and relationship extraction output.

All extraction modules must output data conforming to these schemas so that
downstream graph construction, database storage, and analysis operate on a
consistent format.

Canonical model:
- 12 entity types
- 11 relationship types
- Full provenance on every relationship

This module is intentionally STDLIB-ONLY (no pydantic / third-party deps)
so it runs in any Python 3.9+ environment, including minimal CI containers.

SAFETY NOTE: These schemas describe entities and relationships for an
investigator-assistance system. Nothing here assigns guilt or criminal
labels to individuals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Canonical vocabularies (single source of truth)
# ---------------------------------------------------------------------------

CANONICAL_ENTITY_TYPES = frozenset({
    "Person",
    "Organization",
    "PhoneNumber",
    "Vehicle",
    "Location",
    "FinancialAccount",
    "Transaction",
    "Communication",
    "Case",
    "FIR",
    "Event",
    "Evidence",
})

CANONICAL_RELATIONSHIP_TYPES = frozenset({
    "KNOWS",
    "CALLED",
    "TRANSFERRED_TO",
    "LOCATED_AT",
    "TRAVELED_TO",
    "ASSOCIATED_WITH",
    "WORKS_FOR",
    "OWNS",
    "USED",
    "MENTIONED_IN",
    "RELATED_TO_CASE",
})

CANONICAL_RELATIONSHIP_DIRECTIONS = {
    "KNOWS": "bidirectional",
    "CALLED": "directed",
    "TRANSFERRED_TO": "directed",
    "LOCATED_AT": "directed",
    "TRAVELED_TO": "directed",
    "ASSOCIATED_WITH": "directed",
    "WORKS_FOR": "directed",
    "OWNS": "directed",
    "USED": "directed",
    "MENTIONED_IN": "directed",
    "RELATED_TO_CASE": "directed",
}

# Stable ID prefix per entity type (used by generator + DB seeding + tests)
ENTITY_ID_PREFIXES = {
    "Person": "person",
    "Organization": "org",
    "PhoneNumber": "phone",
    "Vehicle": "vehicle",
    "Location": "location",
    "FinancialAccount": "account",
    "Transaction": "transaction",
    "Communication": "comm",
    "Case": "case",
    "FIR": "fir",
    "Event": "event",
    "Evidence": "evidence",
}

_ID_RE = re.compile(r"^[a-z]+-\d{5}$")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class SchemaValidationError(ValueError):
    """Raised when an entity/relationship violates the canonical schema."""


# ---------------------------------------------------------------------------
# Entity schema
# ---------------------------------------------------------------------------

@dataclass
class EntitySchema:
    """Canonical entity extraction result.

    Stable IDs follow ``{prefix}-{5 digits}`` e.g. ``person-00042``.
    """

    text: str
    entity_type: str
    confidence: float
    extraction_method: str
    start: Optional[int] = None
    end: Optional[int] = None
    normalized_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        errors: List[str] = []
        if self.entity_type not in CANONICAL_ENTITY_TYPES:
            errors.append(
                f"entity_type '{self.entity_type}' not in canonical set")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append(f"confidence {self.confidence} outside [0,1]")
        if not self.text or not isinstance(self.text, str):
            errors.append("text must be a non-empty string")
        if not self.extraction_method:
            errors.append("extraction_method is required (provenance)")
        if self.normalized_id is not None:
            expected = ENTITY_ID_PREFIXES.get(self.entity_type)
            if expected and not self.normalized_id.startswith(expected + "-"):
                errors.append(
                    f"normalized_id '{self.normalized_id}' does not match "
                    f"prefix '{expected}-' for type {self.entity_type}")
            elif not _ID_RE.match(self.normalized_id):
                errors.append(
                    f"normalized_id '{self.normalized_id}' must match "
                    r"^[a-z]+-\d{5}$")
        if self.start is not None and self.end is not None \
                and self.end <= self.start:
            errors.append("end offset must be greater than start offset")
        if errors:
            raise SchemaValidationError("; ".join(errors))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "entity_type": self.entity_type,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "normalized_id": self.normalized_id,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Relationship schema
# ---------------------------------------------------------------------------

@dataclass
class RelationshipSchema:
    """Canonical relationship with FULL PROVENANCE.

    Required provenance fields (task spec):
      relationship_id, source_id, source_type, target_id, target_type,
      timestamp (optional), confidence, extraction_method, created_at.
    """

    source_id: str
    source_type: str
    target_id: str
    target_type: str
    relationship_type: str
    relationship_id: str
    confidence: float
    extraction_method: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat().replace("+00:00", "Z"))
    timestamp: Optional[str] = None  # event time, if known
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        errors: List[str] = []
        if self.source_type not in CANONICAL_ENTITY_TYPES:
            errors.append(f"source_type '{self.source_type}' invalid")
        if self.target_type not in CANONICAL_ENTITY_TYPES:
            errors.append(f"target_type '{self.target_type}' invalid")
        if self.relationship_type not in CANONICAL_RELATIONSHIP_TYPES:
            errors.append(
                f"relationship_type '{self.relationship_type}' invalid")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append(f"confidence {self.confidence} outside [0,1]")
        if not self.relationship_id or not _ID_RE.match(self.relationship_id) \
                or not self.relationship_id.startswith("rel-"):
            errors.append(
                f"relationship_id '{self.relationship_id}' must match rel-XXXXX")
        if not self.extraction_method:
            errors.append("extraction_method is required (provenance)")
        if not self.created_at:
            errors.append("created_at is required (provenance)")
        else:
            try:
                datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"created_at '{self.created_at}' not ISO 8601")
        if self.timestamp is not None:
            try:
                datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"timestamp '{self.timestamp}' not ISO 8601")
        if self.source_id == self.target_id and self.source_type == self.target_type:
            errors.append("self-loop relationships are forbidden")
        # Type-consistency of IDs vs declared types
        for role, etype, eid in (
                ("source", self.source_type, self.source_id),
                ("target", self.target_type, self.target_id)):
            expected = ENTITY_ID_PREFIXES.get(etype)
            if expected and not str(eid).startswith(expected + "-"):
                errors.append(
                    f"{role}_id '{eid}' does not match prefix "
                    f"'{expected}-' for type {etype}")
        if errors:
            raise SchemaValidationError("; ".join(errors))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relationship_id": self.relationship_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "relationship_type": self.relationship_type,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    def to_cypher(self) -> str:
        """Cypher MERGE template for Neo4j ingestion."""
        return (
            f"MATCH (a:{self.source_type} {{entity_id: $source_id}}) "
            f"MATCH (b:{self.target_type} {{entity_id: $target_id}}) "
            f"MERGE (a)-[r:{self.relationship_type} {{"
            f"relationship_id: $relationship_id}}]->(b) "
            f"SET r += $props"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_entity_id(entity_type: str, counter: int) -> str:
    """Stable entity ID: 'person-00001', 'org-00123', ..."""
    prefix = ENTITY_ID_PREFIXES.get(entity_type)
    if prefix is None:
        raise SchemaValidationError(f"unknown entity_type '{entity_type}'")
    return f"{prefix}-{counter:05d}"


def validate_entity_id(entity_id: str, entity_type: str) -> bool:
    """True when the ID prefix matches the declared entity type."""
    prefix = ENTITY_ID_PREFIXES.get(entity_type)
    return bool(prefix) and str(entity_id).startswith(prefix + "-")
