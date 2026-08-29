"""AI/ML module for criminal network analysis.

Provides entity extraction, relationship detection, common canonical
schemas, and deterministic synthetic data generation.

All outputs conform to ai/schemas.EntitySchema and
ai/schemas.RelationshipSchema so downstream storage (PostgreSQL), graph
construction (NetworkX/Neo4j), and analysis share one contract.
"""

from . import entity_extraction
from . import relationship_extraction
from . import schemas
from .schemas import (
    CANONICAL_ENTITY_TYPES,
    CANONICAL_RELATIONSHIP_TYPES,
    CANONICAL_RELATIONSHIP_DIRECTIONS,
    ENTITY_ID_PREFIXES,
    EntitySchema,
    RelationshipSchema,
    SchemaValidationError,
    generate_entity_id,
    validate_entity_id,
)

__all__ = [
    "entity_extraction",
    "relationship_extraction",
    "schemas",
    "CANONICAL_ENTITY_TYPES",
    "CANONICAL_RELATIONSHIP_TYPES",
    "CANONICAL_RELATIONSHIP_DIRECTIONS",
    "ENTITY_ID_PREFIXES",
    "EntitySchema",
    "RelationshipSchema",
    "SchemaValidationError",
    "generate_entity_id",
    "validate_entity_id",
]
