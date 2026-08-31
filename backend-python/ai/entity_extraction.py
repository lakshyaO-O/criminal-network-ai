"""Entity extraction from crime reports and intelligence text.

Uses the canonical EntitySchema so downstream graph/DB modules
can operate on a consistent format.
"""

import re
from typing import List

from .schemas import EntitySchema, generate_entity_id

_TYPE_COUNTERS: dict = {}


def _stable_id(entity_type: str) -> str:
    """Deterministic per-process sequential stable ID (prefix-XXXXX)."""
    _TYPE_COUNTERS[entity_type] = _TYPE_COUNTERS.get(entity_type, 0) + 1
    return generate_entity_id(entity_type, _TYPE_COUNTERS[entity_type])


def extract_entities(text: str) -> List[EntitySchema]:
    """Extract named entities from text using pattern-based matching.

    Args:
        text: Raw crime report or intelligence text.

    Returns:
        List of EntitySchema objects with consistent canonical format.
    """
    entities: list[EntitySchema] = []

    # Pattern-based extraction for demonstration
    # In production, integrate spaCy/stanza NER models (NOT in this milestone)
    patterns = {
        "Person": r"[A-Z][a-z]+\s+[A-Z][a-z]+",
        "Organization": r"[A-Z][a-z]+\s+(?:Corp|Inc|Ltd|Association)",
        "Location": r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*",
    }

    for entity_type, pattern in patterns.items():
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            entities.append(
                EntitySchema(
                    text=match.group(),
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.7,
                    extraction_method="pattern",
                    normalized_id=_stable_id(entity_type),
                )
            )

    for entity in entities:
        entity.validate()

    return entities


if __name__ == "__main__":
    demo = (
        "Report: Rhea Verma contacted Silverline Traders Ltd regarding "
        "the Sector 12 Market incident."
    )
    for e in extract_entities(demo):
        print(e.to_dict())