"""Graph repository package — storage-neutral access to the network graph."""

from .base import GraphRepository, GraphRepositoryError, GraphStats
from .memory import InMemoryGraphRepository

__all__ = [
    "GraphRepository",
    "GraphRepositoryError",
    "GraphStats",
    "InMemoryGraphRepository",
]


def __getattr__(name):  # lazy optional dependency
    if name == "Neo4jGraphRepository":
        from .neo4j_repo import Neo4jGraphRepository

        return Neo4jGraphRepository
    raise AttributeError(name)
