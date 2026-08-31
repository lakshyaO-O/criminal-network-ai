"""Deterministic relationship extraction — Milestone 3.

Principle (per milestone spec): a relationship is NEVER created merely
because two entities occur in the same document. Every relationship must
be produced by an EXPLICIT extraction rule with an explicit textual cue
or a structured source record.

Each rule declares:
- canonical relationship_type,
- endpoint types,
- cue regex(es) that must appear between/around the mentions,
- a FIXED declared prior confidence (documented, not fabricated).

Result records contain:
    relationship_id, source{entity_id,entity_type,text},
    target{...}, timestamp (if available), confidence,
    extraction_method, source_id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .extraction.base import ExtractedEntity

_REL_ID_RE = re.compile(r"^rel-\d{5}$")


@dataclass
class RuleRelationship:
    relationship_id: str
    source_entity_id: Optional[str]
    source_type: str
    source_text: str
    target_entity_id: Optional[str]
    target_type: str
    target_text: str
    relationship_type: str
    confidence: float
    extraction_method: str
    timestamp: Optional[str] = None
    source_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relationship_id": self.relationship_id,
            "source": {
                "entity_id": self.source_entity_id,
                "entity_type": self.source_type,
                "text": self.source_text,
            },
            "target": {
                "entity_id": self.target_entity_id,
                "entity_type": self.target_type,
                "text": self.target_text,
            },
            "relationship_type": self.relationship_type,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "source_id": self.source_id,
            "metadata": dict(self.metadata),
        }


# Declared rule priors (see docs/ai-pipeline.md). Fixed constants tied to
# rule strictness — NOT learned or invented per result.
# M14: Added priors for expanded deterministic coverage (KNOWS, USED, TRANSFERRED_TO text, LOCATED_AT text)
RULE_PRIORS = {
    "works_for_cue": 0.80,
    "called_cue": 0.75,
    "transferred_to_structured": 1.00,  # structured transaction record
    "transferred_to_text": 0.78,  # M14: account-account via text cue
    "traveled_to_cue": 0.75,
    "owns_cue": 0.80,
    "associated_with_cue": 0.70,
    "located_at_structured": 0.90,
    "knows_cue": 0.55,  # M14: conservative person-person
    "used_cue": 0.68,  # M14: person-vehicle
    "located_at_text": 0.65,  # M14: person/location via explicit located cue
}

_CUE_WORKS = re.compile(
    r"\b(?:works?\s+(?:for|at|with)|employed\s+(?:by|at)|employee\s+of)\b",
    re.IGNORECASE)
_CUE_CALLED = re.compile(
    r"\b(?:called|phoned|rang|contacted\s+by\s+phone)\b", re.IGNORECASE)
_CUE_TRANSFERRED = re.compile(
    r"\b(?:transfer(?:red)?|sent|paid)\b.*\b(?:to|into)\b"
    r"|\bto\b.*\b(?:transfer|payment)\b", re.IGNORECASE)
_CUE_TRANSFERRED_TEXT = re.compile(
    r"\b(?:transferred|transfer|sent|paying|paid)\b", re.IGNORECASE)
_CUE_TRAVELED = re.compile(
    r"\b(?:traveled|travelled|went|drove|flew)\s+to\b", re.IGNORECASE)
_CUE_OWNS = re.compile(
    r"\b(?:owns|owned\s+by|owner\s+of|registered\s+to)\b", re.IGNORECASE)
_CUE_ASSOCIATED = re.compile(
    r"\b(?:associated\s+with|affiliated\s+with|linked\s+to|member\s+of)\b",
    re.IGNORECASE)
_CUE_KNOWS = re.compile(
    r"\b(?:knows|know|knew|knowing|acquainted with|met|introduced to)\b", re.IGNORECASE)
_CUE_USED = re.compile(
    r"\b(?:used|using|utilized|driven|drove|operated|operating)\b", re.IGNORECASE)
_CUE_LOCATED_TEXT = re.compile(
    r"\b(?:located at|located in|resides at|stayed at|present at|observed at)\b", re.IGNORECASE)


def _cue_between(text: str, start_a: int, end_a: int,
                 start_b: int, end_b: int, cue: re.Pattern) -> bool:
    """True when the cue appears in the span joining two mentions."""
    lo, hi = min(end_a, end_b), max(start_a, start_b)
    if hi <= lo:
        return False
    window = text[lo:hi]
    return bool(cue.search(window))


class RelationshipExtractor:
    """Interface for relationship-extraction engines."""

    engine = "base"

    def extract_relationships(
        self,
        entities: List[ExtractedEntity],
        text: str,
        source_id: Optional[str] = None,
        structured_records: Optional[List[Dict[str, Any]]] = None,
        id_generator=None,
    ) -> List[RuleRelationship]:
        raise NotImplementedError


class RuleBasedRelationshipExtractor(RelationshipExtractor):
    """Cue-driven deterministic rules over extracted entity mentions."""

    engine = "rules"

    def __init__(self, id_generator=None):
        # id_generator() -> 'rel-XXXXX'; injectable for determinism/tests.
        self._id_generator = id_generator or _sequential_ids()

    def extract_relationships(
        self,
        entities: List[ExtractedEntity],
        text: str,
        source_id: Optional[str] = None,
        structured_records: Optional[List[Dict[str, Any]]] = None,
        id_generator=None,
    ) -> List[RuleRelationship]:
        gen = id_generator or self._id_generator
        results: List[RuleRelationship] = []
        by_type: Dict[str, List[ExtractedEntity]] = {}
        for ent in entities:
            by_type.setdefault(ent.entity_type, []).append(ent)

        def add(src: ExtractedEntity, tgt: ExtractedEntity,
                rel_type: str, method: str, prior: float) -> None:
            results.append(RuleRelationship(
                relationship_id=gen(),
                source_entity_id=src.entity_id,
                source_type=src.entity_type,
                source_text=src.text,
                target_entity_id=tgt.entity_id,
                target_type=tgt.entity_type,
                target_text=tgt.text,
                relationship_type=rel_type,
                confidence=prior,
                extraction_method=f"rule:{method}",
                source_id=source_id or src.source_id,
                metadata={"cue_window_verified": True},
            ))

        persons = by_type.get("Person", [])
        orgs = by_type.get("Organization", [])
        phones = by_type.get("PhoneNumber", [])
        vehicles = by_type.get("Vehicle", [])
        locations = by_type.get("Location", [])
        accounts = by_type.get("FinancialAccount", [])

        # WORKS_FOR: person --works for/at/with--> organization
        for p in persons:
            for o in orgs:
                if _cue_between(text, p.start_offset, p.end_offset,
                                 o.start_offset, o.end_offset, _CUE_WORKS):
                    add(p, o, "WORKS_FOR", "works_for_cue",
                        RULE_PRIORS["works_for_cue"])

        # CALLED: person --called/phoned--> person | phone mention nearby
        for p in persons:
            for q in persons:
                if p is q or p.start_offset >= q.start_offset:
                    continue
                if _cue_between(text, p.start_offset, p.end_offset,
                                 q.start_offset, q.end_offset, _CUE_CALLED):
                    add(p, q, "CALLED", "called_cue",
                        RULE_PRIORS["called_cue"])

        # KNOWS: conservative person-person (M14) — requires explicit knows cue, low confidence
        for p in persons:
            for q in persons:
                if p is q or p.start_offset >= q.start_offset:
                    continue
                if _cue_between(text, p.start_offset, p.end_offset,
                                 q.start_offset, q.end_offset, _CUE_KNOWS):
                    add(p, q, "KNOWS", "knows_cue", RULE_PRIORS["knows_cue"])

        # TRAVELED_TO: person --traveled/went to--> location
        for p in persons:
            for loc in locations:
                if _cue_between(text, p.start_offset, p.end_offset,
                                 loc.start_offset, loc.end_offset,
                                 _CUE_TRAVELED):
                    add(p, loc, "TRAVELED_TO", "traveled_to_cue",
                        RULE_PRIORS["traveled_to_cue"])

        # LOCATED_AT text (M14): person --located at--> location (explicit cue only, both resolved)
        for p in persons:
            for loc in locations:
                if p.entity_id is None or loc.entity_id is None:
                    continue
                if _cue_between(text, p.start_offset, p.end_offset,
                                 loc.start_offset, loc.end_offset, _CUE_LOCATED_TEXT):
                    add(p, loc, "LOCATED_AT", "located_at_text", RULE_PRIORS["located_at_text"])

        # OWNS: person --owns/registered to--> vehicle
        for p in persons:
            for v in vehicles:
                if _cue_between(text, p.start_offset, p.end_offset,
                                 v.start_offset, v.end_offset, _CUE_OWNS):
                    add(p, v, "OWNS", "owns_cue", RULE_PRIORS["owns_cue"])

        # USED (M14): person --used--> vehicle (lower confidence, needs_review, both resolved)
        for p in persons:
            for v in vehicles:
                if p.entity_id is None or v.entity_id is None:
                    continue
                if _cue_between(text, p.start_offset, p.end_offset,
                                 v.start_offset, v.end_offset, _CUE_USED):
                    add(p, v, "USED", "used_cue", RULE_PRIORS["used_cue"])

        # ASSOCIATED_WITH: person --associated/affiliated/member of--> org
        for p in persons:
            for o in orgs:
                if _cue_between(text, p.start_offset, p.end_offset,
                                 o.start_offset, o.end_offset,
                                 _CUE_ASSOCIATED):
                    add(p, o, "ASSOCIATED_WITH", "associated_with_cue",
                        RULE_PRIORS["associated_with_cue"])

        # TRANSFERRED_TO text (M14): FinancialAccount -> FinancialAccount via transfer cue (both resolved)
        for a in accounts:
            for b in accounts:
                if a is b or a.start_offset >= b.start_offset:
                    continue
                if a.entity_id is None or b.entity_id is None:
                    continue
                if _cue_between(text, a.start_offset, a.end_offset,
                                 b.start_offset, b.end_offset, _CUE_TRANSFERRED_TEXT):
                    add(a, b, "TRANSFERRED_TO", "transferred_to_text", RULE_PRIORS["transferred_to_text"])

        # Structured sources: transactions are authoritative evidence of
        # TRANSFERRED_TO between accounts — no text cues required.
        for rec in structured_records or []:
            rel = self._structured_relationship(rec, gen)
            if rel is not None:
                results.append(rel)

        return results

    @staticmethod
    def _structured_relationship(rec: Dict[str, Any],
                                 gen) -> Optional[RuleRelationship]:
        kind = rec.get("record_type")
        if kind == "transaction":
            src, tgt = rec.get("from_account_id"), rec.get("to_account_id")
            if not src or not tgt or src == tgt:
                return None
            return RuleRelationship(
                relationship_id=rec.get("relationship_id") or gen(),
                source_entity_id=src,
                source_type="FinancialAccount",
                source_text=str(rec.get("amount", "")),
                target_entity_id=tgt,
                target_type="FinancialAccount",
                target_text="",
                relationship_type="TRANSFERRED_TO",
                confidence=RULE_PRIORS["transferred_to_structured"],
                extraction_method="rule:transferred_to_structured",
                timestamp=rec.get("timestamp"),
                source_id=rec.get("transaction_id"),
                metadata={"currency": rec.get("currency")},
            )
        if kind == "event_location":
            eid, loc = rec.get("entity_id"), rec.get("location_id")
            if not eid or not loc or eid == loc:
                return None
            return RuleRelationship(
                relationship_id=gen(),
                source_entity_id=eid,
                source_type=str(rec.get("entity_type", "Event")),
                source_text=str(rec.get("name", "")),
                target_entity_id=loc,
                target_type="Location",
                target_text="",
                relationship_type="LOCATED_AT",
                confidence=RULE_PRIORS["located_at_structured"],
                extraction_method="rule:located_at_structured",
                timestamp=rec.get("timestamp"),
                source_id=rec.get("event_id"),
            )
        return None


def _sequential_ids():
    counter = {"rel": 0}

    def gen() -> str:
        counter["rel"] += 1
        return f"rel-{counter['rel']:05d}"

    return gen
