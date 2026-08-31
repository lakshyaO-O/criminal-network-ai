"""spaCy-based entity extractor — OPTIONAL dependency.

Design notes:
- spaCy is imported LAZILY; this module can be imported even when spaCy
  (or its model) is not installed. Instantiation without the dependency
  raises :class:`SpacyUnavailableError`, and ``is_available()`` lets the
  API layer degrade gracefully to the pattern extractor.
- spaCy's default English model does NOT know our domain-specific
  entity types (PhoneNumber, Vehicle registration, FinancialAccount,
  SYN-CASE numbers...). Strategy:
    1. run spaCy NER for generic types (PERSON -> Person, ORG ->
       Organization, LOC/GPE -> Location),
    2. delegate structured types to the PatternEntityExtractor rules.
  Confidence comes from spaCy's model only where a model actually
  produced it; pattern-rule priors are declared constants.
"""

from __future__ import annotations

from typing import List, Optional

from ..entity_resolution import EntityIndex
from .base import EntityExtractor, ExtractedEntity
from .pattern_extractor import PatternEntityExtractor

# Map spaCy labels -> canonical types we accept from the model.
SPACY_LABEL_MAP = {
    "PERSON": "Person",
    "ORG": "Organization",
    "LOC": "Location",
    "GPE": "Location",
}

try:  # pragma: no cover - depends on environment
    import spacy  # type: ignore

    SPACY_INSTALLED = True
except ImportError:  # spaCy not installed (e.g. no wheel for this Python)
    spacy = None  # type: ignore[assignment]
    SPACY_INSTALLED = False


class SpacyUnavailableError(RuntimeError):
    """Raised when spaCy or the requested model is not available."""


def is_available(model_name: str = "en_core_web_sm") -> bool:
    if not SPACY_INSTALLED:
        return False
    try:
        spacy.load(model_name)  # type: ignore[union-attr]
        return True
    except Exception:
        return False


class SpacyEntityExtractor(EntityExtractor):
    """spaCy NER + structural-pattern fallback for domain-specific types."""

    engine = "spacy"

    def __init__(self, model_name: str = "en_core_web_sm",
                 known_entities: Optional[EntityIndex] = None):
        if not SPACY_INSTALLED:
            raise SpacyUnavailableError(
                "spaCy is not installed for this Python interpreter. "
                "Install with: pip install spacy && python -m spacy download "
                f"{model_name}. The PatternEntityExtractor remains fully "
                "functional without it.")
        try:
            self._nlp = spacy.load(model_name)  # type: ignore[union-attr]
        except Exception as exc:  # OSError for missing models
            raise SpacyUnavailableError(
                f"spaCy model '{model_name}' could not be loaded: {exc}")

        self.model_name = model_name
        self._patterns = PatternEntityExtractor(known_entities=known_entities)
        self.known_entities = known_entities

    @property
    def description(self) -> str:
        return (f"spaCy '{self.model_name}' NER for Person/Organization/"
                "Location plus deterministic patterns for structured "
                "domain types.")

    def supports(self, entity_type: str) -> bool:
        return (entity_type in SPACY_LABEL_MAP.values()
                or self._patterns.supports(entity_type))

    def extract(self, text: str,
                source_id: Optional[str] = None) -> List[ExtractedEntity]:
        results: List[ExtractedEntity] = []
        doc = self._nlp(text)

        for ent in doc.ents:
            entity_type = SPACY_LABEL_MAP.get(ent.label_)
            if entity_type is None:
                continue
            known_id = None
            if self.known_entities is not None:
                known_id = self.known_entities.find_known_id(
                    ent.text, entity_type)
            results.append(ExtractedEntity(
                text=ent.text,
                entity_type=entity_type,
                start_offset=ent.start_char,
                end_offset=ent.end_char,
                normalized_value=ent.text.strip(),
                entity_id=known_id,
                confidence=None,  # spaCy gives label, not calibrated score
                extraction_method=f"spacy:{self.model_name}:{ent.label_}",
                source_id=source_id,
            ))

        # Structured/domain types via deterministic patterns.
        results.extend(self._patterns.extract(text, source_id=source_id))
        return sorted(results, key=lambda e: (e.start_offset, -e.end_offset))
