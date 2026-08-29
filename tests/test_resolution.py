"""Tests for deterministic entity resolution (Milestone 3)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.entity_resolution import (
    DeterministicEntityResolver,
    EntityIndex,
    ResolutionCandidate,
)


def load_index():
    import json
    DATA_DIR = Path(__file__).parent.parent / "data" / "synthetic"
    dataset = {}
    for json_file in DATA_DIR.glob("*.json"):
        if json_file.name.startswith("_"):
            continue
        with json_file.open() as f:
            dataset[json_file.stem] = json.load(f)
    index = EntityIndex.from_dataset(dataset)
    # Ensure deterministic test fixtures exist regardless of random dataset content.
    # These mirror the synthetic namespace but are explicitly injected for test stability.
    # Use distinct IDs that do not collide with existing dataset IDs.
    from ai.entity_resolution import normalize_phone
    if not index._by_phone.get(normalize_phone("+91-901234567")):
        index.add_phone("phone-99901", "+91-901234567")
    if not index._by_account.get("FICA12345678"):
        index.add_account("account-99901", "FICA12345678")
    if not index._by_vehicle.get("DL-FIC12-AB1234"):
        index.add_vehicle("vehicle-99901", "DL-FIC12-AB1234")
    # Person/org names are normalized; ensure they exist for resolution tests
    from ai.entity_resolution import normalize_person_name, normalize_org_name
    if not index._by_person_name.get(normalize_person_name("Rhea Verma")):
        index.add_person("person-99901", "Rhea Verma")
    if not index._by_person_name.get(normalize_person_name("Kabir Rao")):
        index.add_person("person-99902", "Kabir Rao")
    if not index._by_org_name.get(normalize_org_name("Bluepeak Traders Pvt Ltd")):
        index.add_organization("org-99901", "Bluepeak Traders Pvt Ltd")
    return index


def test_exact_phone_resolution():
    index = load_index()
    resolver = DeterministicEntityResolver(index)

    # Exact fictional phone format
    candidates = resolver.resolve("+91-901234567", "PhoneNumber")
    assert len(candidates) == 1
    c = candidates[0]
    assert c.match_method == "exact_normalized_phone"
    assert c.confidence == 1.0
    assert c.status == "auto_linked"
    assert c.candidate_entity_id.startswith("phone-")


def test_exact_account_resolution():
    index = load_index()
    resolver = DeterministicEntityResolver(index)

    candidates = resolver.resolve("FICA12345678", "FinancialAccount")
    assert len(candidates) == 1
    c = candidates[0]
    assert c.match_method == "exact_account_number"
    assert c.confidence == 1.0
    assert c.status == "auto_linked"
    assert c.candidate_entity_id.startswith("account-")


def test_exact_vehicle_resolution():
    index = load_index()
    resolver = DeterministicEntityResolver(index)

    candidates = resolver.resolve("DL-FIC12-AB1234", "Vehicle")
    assert len(candidates) == 1
    c = candidates[0]
    assert c.match_method == "exact_vehicle_identifier"
    assert c.confidence == 1.0
    assert c.status == "auto_linked"
    assert c.candidate_entity_id.startswith("vehicle-")


def test_person_name_resolution_always_review():
    index = load_index()
    resolver = DeterministicEntityResolver(index)

    # Name normalization should find the canonical entity
    candidates = resolver.resolve("Rhea Verma", "Person")
    assert len(candidates) >= 1
    for c in candidates:
        assert c.match_method == "normalized_person_name"
        assert c.confidence == 0.60  # DECLARED_NAME_MATCH_CONFIDENCE
        # Names are inherently ambiguous -> ALWAYS needs_review
        assert c.status == "needs_review"


def test_org_name_resolution_always_review():
    index = load_index()
    resolver = DeterministicEntityResolver(index)

    candidates = resolver.resolve("Bluepeak Traders Pvt Ltd", "Organization")
    assert len(candidates) >= 1
    for c in candidates:
        assert c.match_method == "normalized_org_name"
        assert c.confidence == 0.60
        assert c.status == "needs_review"


def test_unknown_type_no_candidates():
    index = load_index()
    resolver = DeterministicEntityResolver(index)

    candidates = resolver.resolve("some-value", "Transaction")
    assert candidates == []


def test_candidate_to_dict():
    c = ResolutionCandidate(
        candidate_entity_id="person-00001",
        match_method="exact_normalized_phone",
        confidence=1.0,
        supporting_fields=["number"],
        status="auto_linked",
    )
    d = c.to_dict()
    assert d["candidate_entity_id"] == "person-00001"
    assert d["status"] == "auto_linked"


if __name__ == "__main__":
    test_exact_phone_resolution()
    test_exact_account_resolution()
    test_exact_vehicle_resolution()
    test_person_name_resolution_always_review()
    test_org_name_resolution_always_review()
    test_unknown_type_no_candidates()
    test_candidate_to_dict()
    print("All entity resolution tests passed")