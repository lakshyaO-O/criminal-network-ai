"""Pattern-based entity extractor (deterministic, always available).

Every match is labeled ``extraction_method="pattern:<rule>"`` so pattern
provenance is explicit. Confidence values are FIXED RULE PRIORS declared
in :data:`RULE_PRIORS` — they are deterministic constants, not model
scores and never fabricated per-result.

When an :class:`ai.entity_resolution.EntityIndex` is provided, mentions
that already exist in the canonical corpus get their stable ``entity_id``
attached.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional

from ..entity_resolution import EntityIndex
from .base import ENTITY_TYPES, EntityExtractor, ExtractedEntity

# Declared deterministic priors (documented in docs/ai-pipeline.md).
# These express match STRICTNESS of the rule, not a probability of truth.
RULE_PRIORS = {
    "phone_fictional": 0.95,   # strict structural format
    "phone_e164": 0.85,
    "vehicle_registration": 0.90,
    "account_number": 0.95,
    "case_number": 0.95,
    "fir_number": 0.95,
    "org_suffix": 0.80,
    "person_titlecase": 0.40,  # weak heuristic: any Title Case pair
    "location_titlecase": 0.30,
}


@dataclass
class PatternRule:
    name: str
    regex: re.Pattern
    entity_type: str
    normalizer: Optional[Callable[[str], str]] = None


def _clean_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


FICTIONAL_PHONE_RE = r"\+91-(?:9[0-4])-\d{7}"
GENERIC_PHONE_RE = r"\+\d{1,3}[-\s]?\d{7,10}\b"


def _default_rules() -> List[PatternRule]:
    return [
        # Fictional synthetic-corpus phone range first (strictest).
        PatternRule(
            name="phone_fictional",
            regex=re.compile(FICTIONAL_PHONE_RE),
            entity_type="PhoneNumber",
            normalizer=_clean_ws,
        ),
        PatternRule(
            name="phone_e164",
            regex=re.compile(GENERIC_PHONE_RE),
            entity_type="PhoneNumber",
            normalizer=_clean_ws,
        ),
        # Synthetic vehicle registrations: DL-FIC12-AB1234 (+ generic
        # two-state-code Indian style).
        PatternRule(
            name="vehicle_registration",
            regex=re.compile(
                r"\b[A-Z]{2}-FIC\d{2}-[A-Z]{1,3}\d{3,4}\b"
                r"|\b[A-Z]{2}[-\s]\d{1,2}[-\s][A-Z]{1,3}[-\s]\d{3,4}\b"),
            entity_type="Vehicle",
            normalizer=lambda v: v.replace(" ", ""),
        ),
        PatternRule(
            name="account_number",
            regex=re.compile(r"\bFICA\d{8,9}\b"),
            entity_type="FinancialAccount",
        ),
        PatternRule(
            name="case_number",
            regex=re.compile(r"\bSYN-CASE-\d{4}-\d{3}\b"),
            entity_type="Case",
        ),
        PatternRule(
            name="fir_number",
            regex=re.compile(r"\bSYN-FIR-\d{4}-\d{4}\b"),
            entity_type="FIR",
        ),
        PatternRule(
            name="org_suffix",
            regex=re.compile(
                r"\b([A-Z][\w&]*\s+){1,3}"
                r"(?:Traders|Logistics|Enterprises|Services|Solutions|"
                r"Industries|Associates|Imports\s*&\s*Exports)\s+"
                r"(?:Pvt Ltd|LLP|Ltd|Inc|Corp)?\b"),
            entity_type="Organization",
            normalizer=_clean_ws,
        ),
        PatternRule(
            name="person_titlecase",
            regex=re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b"),
            entity_type="Person",
            normalizer=_clean_ws,
        ),
        PatternRule(
            name="location_titlecase",
            regex=re.compile(
                r"\b(?:Sector|Ring Road|Old Fort Road|Lake View Colony|"
                r"Station Square|Mill Lane|Garden Chowk|Riverside Depot|"
                r"Tech Park Gate|Hillview Apartments)\b"
                r"(?:\s+(?:\d+|[A-Z][a-z]+))*"),
            entity_type="Location",
            normalizer=_clean_ws,
        ),
    ]


class PatternEntityExtractor(EntityExtractor):
    """Deterministic regex/structural extraction.

    Supported types are exactly those with at least one rule; the full
    canonical set is accepted by the contract but only detectable types
    are reported by :meth:`supports`.
    """

    engine = "pattern"

    def __init__(self,
                 known_entities: Optional[EntityIndex] = None,
                 rules: Optional[List[PatternRule]] = None):
        self.known_entities = known_entities
        self.rules = rules if rules is not None else _default_rules()
        for rule in self.rules:
            if rule.entity_type not in ENTITY_TYPES:
                raise ValueError(f"rule '{rule.name}' has invalid type "
                                 f"{rule.entity_type}")
            if rule.name not in RULE_PRIORS:
                raise ValueError(f"rule '{rule.name}' has no declared prior")

    @property
    def description(self) -> str:
        return ("Deterministic pattern-based extraction; confidence values "
                "are fixed declared rule priors, not model scores.")

    def supports(self, entity_type: str) -> bool:
        return any(r.entity_type == entity_type for r in self.rules)

    def extract(self, text: str,
                source_id: Optional[str] = None) -> List[ExtractedEntity]:
        if not isinstance(text, str):
            raise ValueError("text must be a string")

        results: List[ExtractedEntity] = []
        occupied: List[tuple] = []  # suppress overlaps from weaker rules

        def overlaps(start: int, end: int) -> bool:
            return any(not (end <= s or start >= e) for s, e in occupied)

        for rule in self.rules:
            for match in rule.regex.finditer(text):
                surface = match.group()
                if not surface.strip():
                    continue
                start, end = match.span()
                if overlaps(start, end):
                    continue

                normalized = (rule.normalizer(surface)
                              if rule.normalizer else surface)
                known_id = None
                if self.known_entities is not None:
                    known_id = self.known_entities.find_known_id(
                        normalized, rule.entity_type)

                results.append(ExtractedEntity(
                    text=surface,
                    entity_type=rule.entity_type,
                    start_offset=start,
                    end_offset=end,
                    normalized_value=normalized,
                    entity_id=known_id,
                    confidence=RULE_PRIORS[rule.name],
                    extraction_method=f"pattern:{rule.name}",
                    source_id=source_id,
                ))
                occupied.append((start, end))

        for entity in results:
            entity.validate()
        return sorted(results, key=lambda e: (e.start_offset, -e.end_offset))
