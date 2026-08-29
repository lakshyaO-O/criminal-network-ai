"""Persistence package — PostgreSQL (canonical) + In-Memory (tests).

Canonical store: PostgreSQL (structured, provenance-complete)
Analytical projection: Neo4j (relationship/network)
Fallback/test: InMemoryPersistence (no external services)

Usage:
    from ai.persistence import PostgresPersistence, InMemoryPersistence

The InvestigationPipeline accepts any PersistenceSink via dependency injection.
"""

from .base import PersistenceBase, PersistenceError
from .memory import InMemoryPersistence

__all__ = ["PersistenceBase", "PersistenceError", "InMemoryPersistence"]


def __getattr__(name):
    if name == "PostgresPersistence":
        from .postgres import PostgresPersistence

        return PostgresPersistence
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
