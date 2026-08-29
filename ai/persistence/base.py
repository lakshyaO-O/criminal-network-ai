"""Persistence abstraction for Milestone 4.

PostgreSQL is the canonical structured store (12 entity types, 11 relationship
types, full provenance). Neo4j is the analytical projection. In-memory is
the test/development fallback.

All implementations must:
- use parameterized SQL (never string-concatenated user input)
- preserve every provenance field (relationship_id, source_id, source_type, ...)
- be idempotent (same ID → upsert, not duplicate)
- be transaction-safe (write-sets commit atomically)

This module is intentionally DB-driver agnostic at the interface level;
concrete implementations handle driver imports internally.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class PersistenceError(RuntimeError):
    """Raised for persistence failures (connection, constraint, etc.)."""


class PersistenceBase(ABC):
    """Abstract persistence contract for the canonical model."""

    # -- writes (idempotent upserts) ---------------------------------------

    @abstractmethod
    def save_entity(self, entity_id: str, entity_type: str, payload: Dict[str, Any]) -> str:
        """Upsert an entity. Returns 'inserted' or 'updated'."""
        ...

    @abstractmethod
    def save_relationship(self, relationship_id: str, payload: Dict[str, Any]) -> str:
        """Upsert a relationship with full provenance. Returns 'inserted' or 'updated'."""
        ...

    @abstractmethod
    def save_case(self, case_id: str, payload: Dict[str, Any]) -> str:
        """Upsert a case record (used by import)."""
        ...

    @abstractmethod
    def save_evidence(self, evidence_id: str, payload: Dict[str, Any]) -> str:
        """Upsert evidence metadata."""
        ...

    # -- reads -------------------------------------------------------------

    @abstractmethod
    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve entity by stable TEXT ID across all entity tables. Returns None if not found."""
        ...

    @abstractmethod
    def get_relationships(self, entity_id: str) -> List[Dict[str, Any]]:
        """All relationships where entity is source or target."""
        ...

    @abstractmethod
    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """True if the underlying store is reachable and schema present."""
        ...

    # -- transactions ------------------------------------------------------

    @abstractmethod
    def transaction(self):
        """Context manager for transaction-safe multi-write batches.

        Example:
            with persistence.transaction():
                persistence.save_entity(...)
                persistence.save_relationship(...)
        """
        ...
