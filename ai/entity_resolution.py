"""Deterministic entity resolution — Milestone 3.

Goal: decide when multiple mentions likely refer to the SAME canonical
entity, using only deterministic matching rules:

- exact normalized phone number
- exact account number within the synthetic namespace
- exact vehicle identifier
- normalized person name
- normalized organization name

Guarantees:
- NO probabilistic identity model.
- NO automatic merging of ambiguous entities.
- Ambiguous matches are returned as candidates with
  ``status="needs_review"``.

Confidence values are deterministic rule outputs (1.0 for exact
structured-key matches; DECLARED_NAME_MATCH prior for name matches) —
they are not learned or fabricated scores.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

# Declared, documented rule prior — NOT a learned score.
DECLARED_NAME_MATCH_CONFIDENCE = 0.60

AUTO_LINK_THRESHOLD = 0.95  # only exact structured keys auto-link

_PERSON_NAME_RE = re.compile(r"^[a-z]+$")


def normalize_person_name(name: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation."""
    cleaned = re.sub(r"[^\w\s]", " ", name.strip().lower())
    return re.sub(r"\s+", " ", cleaned)


def normalize_org_name(name: str) -> str:
    """Lowercase and drop legal suffixes so 'Bluepeak Traders Pvt Ltd'
    and 'Bluepeak Traders' resolve together."""
    cleaned = normalize_person_name(name)
    suffixes = (
        " pvt ltd", " private limited", " ltd", " limited",
        " llp", " inc", " corp", " associates",
    )
    for suffix in suffixes:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
            break
    return cleaned


def normalize_phone(number: str) -> str:
    """Strip formatting, keep trailing 10 digits as the key."""
    digits = re.sub(r"\D", "", number)
    return digits[-10:] if len(digits) >= 10 else digits


@dataclass(frozen=True)
class EntityRecord:
    """A canonical entity available to the resolver."""

    entity_id: str
    entity_type: str
    display_name: str


@dataclass
class ResolutionCandidate:
    """One candidate canonical entity for a mention."""

    candidate_entity_id: str
    match_method: str
    confidence: float
    supporting_fields: List[str] = field(default_factory=list)
    status: str = "needs_review"  # 'auto_linked' | 'needs_review'

    def to_dict(self) -> dict:
        return {
            "candidate_entity_id": self.candidate_entity_id,
            "match_method": self.match_method,
            "confidence": self.confidence,
            "supporting_fields": self.supporting_fields,
            "status": self.status,
        }


class EntityIndex:
    """In-memory canonical entity index built from structured records.

    Used by the resolvers AND by the pattern extractor to attach a known
    ``entity_id`` when a mention already exists in the corpus.
    """

    def __init__(self) -> None:
        # (match_key, entity_type) -> set of entity_ids
        self._by_phone: Dict[str, set] = {}
        self._by_account: Dict[str, set] = {}
        self._by_vehicle: Dict[str, set] = {}
        self._by_person_name: Dict[str, set] = {}
        self._by_org_name: Dict[str, set] = {}
        self._records: Dict[str, EntityRecord] = {}

        # raw-value lookups for the extractor's known-entity attachment
        self._by_raw_lower: Dict[str, list] = {}

    # -- construction ------------------------------------------------------

    @classmethod
    def from_dataset(cls, dataset: dict) -> "EntityIndex":
        idx = cls()
        for row in dataset.get("persons", []):
            idx.add_person(row["person_id"], row["full_name"])
        for row in dataset.get("organizations", []):
            idx.add_organization(row["org_id"], row["name"])
        for row in dataset.get("phone_numbers", []):
            idx.add_phone(row["phone_id"], row["number"])
        for row in dataset.get("financial_accounts", []):
            idx.add_account(row["account_id"], row["account_number"])
        for row in dataset.get("vehicles", []):
            idx.add_vehicle(row["vehicle_id"], row["registration_number"],
                            vin=row.get("vin"))
        return idx

    # -- registration --------------------------------------------------------

    def _register(self, entity_id: str, entity_type: str,
                  display_name: str) -> None:
        self._records[entity_id] = EntityRecord(
            entity_id=entity_id, entity_type=entity_type,
            display_name=display_name)
        self._by_raw_lower.setdefault(display_name.lower(), []).append(
            entity_id)

    def add_person(self, entity_id: str, full_name: str) -> None:
        self._register(entity_id, "Person", full_name)
        self._by_person_name.setdefault(
            normalize_person_name(full_name), set()).add(entity_id)

    def add_organization(self, entity_id: str, name: str) -> None:
        self._register(entity_id, "Organization", name)
        self._by_org_name.setdefault(
            normalize_org_name(name), set()).add(entity_id)

    def add_phone(self, entity_id: str, number: str) -> None:
        self._register(entity_id, "PhoneNumber", number)
        self._by_phone.setdefault(normalize_phone(number), set()).add(
            entity_id)

    def add_account(self, entity_id: str, account_number: str) -> None:
        self._register(entity_id, "FinancialAccount", account_number)
        self._by_account.setdefault(account_number.strip().upper(),
                                    set()).add(entity_id)

    def add_vehicle(self, entity_id: str, registration_number: str,
                    vin: Optional[str] = None) -> None:
        self._register(entity_id, "Vehicle", registration_number)
        self._by_vehicle.setdefault(registration_number.strip().upper(),
                                    set()).add(entity_id)
        if vin:
            self._by_vehicle.setdefault(vin.strip().upper(),
                                        set()).add(entity_id)

    # -- lookup ---------------------------------------------------------------

    def get_record(self, entity_id: str) -> Optional[EntityRecord]:
        return self._records.get(entity_id)

    def find_known_id(self, surface: str, entity_type: str) -> Optional[str]:
        """Exact raw-surface lookup used by the extractor."""
        ids = self._by_raw_lower.get(surface.lower(), [])
        for eid in ids:
            rec = self._records[eid]
            if rec.entity_type == entity_type:
                return eid
        return None

    def all_records(self) -> Iterable[EntityRecord]:
        return self._records.values()

    def __len__(self) -> int:
        return len(self._records)


class DeterministicEntityResolver:
    """First-pass deterministic resolution against an :class:`EntityIndex`.

    ``resolve`` returns ALL matching candidates. A mention is resolved to
    exactly one entity ONLY on an exact structured key match (phone,
    account, vehicle identifier). Name-based matches always come back as
    candidates requiring review.
    """

    def __init__(self, index: EntityIndex,
                 name_match_confidence: float = DECLARED_NAME_MATCH_CONFIDENCE):
        self.index = index
        self.name_match_confidence = name_match_confidence

    def resolve(self, text: str, entity_type: str,
                normalized_value: Optional[str] = None) -> List[ResolutionCandidate]:
        value = normalized_value if normalized_value is not None else text

        if entity_type == "Person":
            return self._name_candidates(
                self.index._by_person_name,
                normalize_person_name(value),
                method="normalized_person_name")
        if entity_type == "Organization":
            return self._name_candidates(
                self.index._by_org_name,
                normalize_org_name(value),
                method="normalized_org_name")
        if entity_type == "PhoneNumber":
            return self._exact_candidates(
                self.index._by_phone, normalize_phone(value),
                method="exact_normalized_phone",
                supporting_fields=["number"])
        if entity_type == "FinancialAccount":
            return self._exact_candidates(
                self.index._by_account, value.strip().upper(),
                method="exact_account_number",
                supporting_fields=["account_number"])
        if entity_type == "Vehicle":
            return self._exact_candidates(
                self.index._by_vehicle, value.strip().upper(),
                method="exact_vehicle_identifier",
                supporting_fields=["registration_number", "vin"])
        # No deterministic rule for other entity types yet.
        return []

    # -- helpers ----------------------------------------------------------

    def _exact_candidates(self, table: Dict[str, set], key: str,
                          method: str, supporting_fields: List[str]
                          ) -> List[ResolutionCandidate]:
        ids = sorted(table.get(key, ()))
        return [
            ResolutionCandidate(
                candidate_entity_id=eid,
                match_method=method,
                confidence=1.0,
                supporting_fields=list(supporting_fields),
                status="auto_linked" if len(ids) == 1 else "needs_review",
            )
            for eid in ids
        ]

    def _name_candidates(self, table: Dict[str, set], key: str,
                         method: str) -> List[ResolutionCandidate]:
        ids = sorted(table.get(key, ()))
        return [
            ResolutionCandidate(
                candidate_entity_id=eid,
                match_method=method,
                confidence=self.name_match_confidence,
                supporting_fields=["full_name" if method.endswith("person_name")
                                   else "name"],
                # Names are inherently ambiguous -> ALWAYS review.
                status="needs_review",
            )
            for eid in ids
        ]
