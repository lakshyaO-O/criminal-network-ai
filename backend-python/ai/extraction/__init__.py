"""Entity extraction abstractions for SIH 26189.

Defines the ``EntityExtractor`` interface plus the common
``ExtractedEntity`` result contract. Implementations:

- :class:`ai.extraction.pattern_extractor.PatternEntityExtractor`
  deterministic regex/structural rules (always available)
- :class:`ai.extraction.spacy_extractor.SpacyEntityExtractor`
  spaCy NER (optional dependency, lazily imported)

SAFETY: extraction only identifies mentions of entities in authorized
text. It never assigns guilt or criminality labels.
"""

from .base import (
    ENTITY_TYPES,
    EntityExtractor,
    ExtractionError,
    ExtractedEntity,
)
from .pattern_extractor import PatternEntityExtractor
from .spacy_extractor import is_available

__all__ = [
    "ENTITY_TYPES",
    "EntityExtractor",
    "ExtractionError",
    "ExtractedEntity",
    "PatternEntityExtractor",
    "is_available",
]


def __getattr__(name):  # lazy optional dependency
    if name == "SpacyEntityExtractor":
        from .spacy_extractor import SpacyEntityExtractor

        return SpacyEntityExtractor
    raise AttributeError(name)
