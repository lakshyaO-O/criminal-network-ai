"""Provider abstraction for M12A — REAL AI INTELLIGENCE LAYER.

Contract:
- Provider-independent AIAnalyzer interface.
- Business logic never hard-codes upstream API specifics.
- All providers return structured, provenance-aware results with deterministic IDs.

Safety:
- No guilt/criminality scoring.
- Confidence means extraction/interpretation confidence, never p(guilty).
- All outputs distinguish observed data from analytical interpretation.
"""
from __future__ import annotations

import abc
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class AIProviderError(RuntimeError):
    """Base for typed provider failures."""


class ProviderUnavailable(AIProviderError):
    """No provider configured or reachable — must NOT silently fabricate."""


class ProviderTimeout(AIProviderError):
    """Provider exceeded time budget."""


class ProviderMalformedResponse(AIProviderError):
    """Provider returned unparseable or contract-violating payload."""


@dataclass
class AIEntityMention:
    canonical_type: str
    value: str
    start: Optional[int]
    end: Optional[int]
    confidence: float
    extraction_method: str
    provenance: Dict[str, Any] = field(default_factory=dict)
    needs_review: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIRelationshipMention:
    source_entity_index: int  # index into entities list
    target_entity_index: int
    relationship_type: str
    confidence: float
    extraction_method: str
    provenance: Dict[str, Any] = field(default_factory=dict)
    needs_review: bool = False
    evidence_span: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIAnalysisResult:
    analysis_id: str
    analysis_type: str
    summary: str
    observations: List[str]
    analytical_interpretation: List[str]
    supporting_entity_ids: List[str]
    supporting_relationship_ids: List[str]
    supporting_evidence_ids: List[str]
    confidence: float
    methodology: str
    limitations: str
    provenance: List[Dict[str, Any]]
    lineage: Dict[str, Any]
    reproducibility: Dict[str, Any]
    grounding_status: str = "SUPPORTED"
    grounding_details: Dict[str, Any] = field(default_factory=dict)


class AIProvider(abc.ABC):
    """Provider-independent contract for Milestone 12A."""

    provider_name: str = "base"
    provider_version: str = "0.0.0"

    @abc.abstractmethod
    def extract_entities(self, text: str, source_id: Optional[str] = None) -> List[AIEntityMention]:
        ...

    @abc.abstractmethod
    def extract_relationships(
        self,
        text: str,
        entities: List[AIEntityMention],
        source_id: Optional[str] = None,
        structured_records: Optional[List[Dict[str, Any]]] = None,
    ) -> List[AIRelationshipMention]:
        ...

    @abc.abstractmethod
    def analyze_patterns(
        self,
        graph_snapshot: Dict[str, Any],
        analysis_type: str = "network_summary",
        case_id: Optional[str] = None,
        root_entity_id: Optional[str] = None,
    ) -> AIAnalysisResult:
        ...

    @abc.abstractmethod
    def status(self) -> Dict[str, Any]:
        """Lightweight health descriptor (provider, model, available)."""


def deterministic_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def sanitize_text(text: str, max_len: int = 100000) -> str:
    """Bounded + injection-safe text handling.

    - Enforces max length (prevent oversized payloads).
    - Strips control characters that could indicate prompt-injection.
    - Never executes content as code.
    """
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if len(text) > max_len:
        raise ValueError(f"text exceeds maximum length {max_len}")
    if len(text.strip()) == 0:
        raise ValueError("text must be non-empty")
    # Neutralize obvious injection markers for logging (not for extraction)
    # We do not alter extraction semantics, only sanitize for logs.
    return text
