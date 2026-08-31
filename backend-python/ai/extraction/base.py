"""Core extraction contracts.

``ExtractedEntity`` is the pipeline-level mention record. It is distinct
from :class:`ai.schemas.EntitySchema` (the canonical storage contract):
extraction results may have ``entity_id=None`` until entity resolution
links them to a canonical entity, and ``confidence=None`` when no score
is justified. Confidence values are NEVER fabricated: pattern rules use
explicit, documented rule priors; statistical/learned scores must come
from an actual model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ENTITY_TYPES = (
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
)


class ExtractionError(ValueError):
    """Raised for invalid extractor configuration or input."""


@dataclass
class ExtractedEntity:
    """A single entity mention found in a source text/record.

    Attributes:
        text: raw surface form as it appeared in the source.
        entity_type: canonical entity type (one of ENTITY_TYPES).
        start_offset / end_offset: character offsets in the source.
        normalized_value: normalized form used for matching/resolution.
        entity_id: canonical stable ID if already known, else None.
        confidence: None unless an explicit rule prior or model score
            exists. Never invented.
        extraction_method: e.g. ``pattern:phone_e164`` or ``spacy:en_core_web_sm``.
            Pattern-based extractors MUST identify themselves as such.
        source_id: identifier of the document/record the mention came from.
        metadata: additional provenance-free context.
    """

    text: str
    entity_type: str
    start_offset: int
    end_offset: int
    normalized_value: Optional[str] = None
    entity_id: Optional[str] = None
    confidence: Optional[float] = None
    extraction_method: str = ""
    source_id: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        errors = []
        if self.entity_type not in ENTITY_TYPES:
            errors.append(f"entity_type '{self.entity_type}' not supported")
        if not self.text:
            errors.append("text must be non-empty")
        if self.end_offset <= self.start_offset:
            errors.append("end_offset must be greater than start_offset")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence outside [0,1]")
        if not self.extraction_method:
            errors.append("extraction_method is required")
        if errors:
            raise ExtractionError("; ".join(errors))

    def to_dict(self) -> Dict[str, object]:
        return {
            "text": self.text,
            "entity_type": self.entity_type,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "normalized_value": self.normalized_value,
            "entity_id": self.entity_id,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "source_id": self.source_id,
            "metadata": dict(self.metadata),
        }


class EntityExtractor(ABC):
    """Interface all entity-extraction engines must implement.

    A future transformer-based implementation can be dropped in without
    changing API contracts: it only needs to return ExtractedEntity items.
    """

    #: short engine name, e.g. "pattern", "spacy"
    engine: str = "base"

    @abstractmethod
    def extract(self, text: str, source_id: Optional[str] = None) -> List[ExtractedEntity]:
        """Extract entity mentions from ``text``."""

    @abstractmethod
    def supports(self, entity_type: str) -> bool:
        """True if this engine can detect the given canonical type."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the engine (for API responses)."""
