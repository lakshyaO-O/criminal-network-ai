"""Tests for entity and relationship extraction (Milestone 3)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend-python"))

from ai.entity_resolution import EntityIndex
from ai.extraction import PatternEntityExtractor, is_available
from ai.relationship_rules import RuleBasedRelationshipExtractor


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
    # Ensure deterministic test fixtures exist (see test_resolution.py)
    from ai.entity_resolution import normalize_phone, normalize_person_name, normalize_org_name
    if not index._by_phone.get(normalize_phone("+91-901234567")):
        index.add_phone("phone-99901", "+91-901234567")
    if not index._by_account.get("FICA12345678"):
        index.add_account("account-99901", "FICA12345678")
    if not index._by_vehicle.get("DL-FIC12-AB1234"):
        index.add_vehicle("vehicle-99901", "DL-FIC12-AB1234")
    if not index._by_person_name.get(normalize_person_name("Rhea Verma")):
        index.add_person("person-99901", "Rhea Verma")
    if not index._by_person_name.get(normalize_person_name("Kabir Rao")):
        index.add_person("person-99902", "Kabir Rao")
    if not index._by_org_name.get(normalize_org_name("Bluepeak Traders Pvt Ltd")):
        index.add_organization("org-99901", "Bluepeak Traders Pvt Ltd")
    return index


def test_pattern_entity_extractor():
    index = load_index()
    extractor = PatternEntityExtractor(known_entities=index)

    text = (
        "Rhea Verma called +91-901234567 about the case SYN-CASE-2024-001. "
        "Vehicle DL-FIC12-AB1234 was seen at Sector 12 Market. "
        "Account FICA12345678 received funds."
    )
    entities = extractor.extract(text, source_id="ext-test-001")

    assert len(entities) >= 6
    types = {e.entity_type for e in entities}
    assert "Person" in types
    assert "PhoneNumber" in types
    assert "Case" in types
    assert "Vehicle" in types
    assert "Location" in types
    assert "FinancialAccount" in types

    # All entities must have extraction_method starting with "pattern:"
    for e in entities:
        assert e.extraction_method.startswith("pattern:")
        # Confidence is a declared prior
        assert e.confidence is not None
        assert 0.0 <= e.confidence <= 1.0

    # Known entity attachment
    person = next(e for e in entities if e.entity_type == "Person")
    assert person.entity_id is not None
    assert person.entity_id.startswith("person-")


def test_extractor_supports():
    index = load_index()
    extractor = PatternEntityExtractor(known_entities=index)
    assert extractor.supports("Person")
    assert extractor.supports("PhoneNumber")
    assert extractor.supports("Vehicle")
    assert extractor.supports("FinancialAccount")
    assert extractor.supports("Case")
    assert extractor.supports("FIR")
    # Unsupported types (no rule yet)
    assert not extractor.supports("Transaction")
    assert not extractor.supports("Communication")
    assert not extractor.supports("Event")
    assert not extractor.supports("Evidence")


def test_relationship_extractor():
    index = load_index()
    extractor = PatternEntityExtractor(known_entities=index)
    rel_extractor = RuleBasedRelationshipExtractor()

    text = (
        "Rhea Verma works for Bluepeak Traders Pvt Ltd. "
        "Rhea Verma called Kabir Rao. "
        "Rhea Verma traveled to Sector 12 Market. "
        "Rhea Verma owns vehicle DL-FIC12-AB1234."
    )
    entities = extractor.extract(text, source_id="rel-test-001")
    rels = rel_extractor.extract_relationships(entities, text, source_id="rel-test-001")

    assert len(rels) >= 4
    types = {r.relationship_type for r in rels}
    assert "WORKS_FOR" in types
    assert "CALLED" in types
    assert "TRAVELED_TO" in types
    assert "OWNS" in types

    for r in rels:
        assert r.extraction_method.startswith("rule:")
        assert 0.0 <= r.confidence <= 1.0


def test_structured_relationship_from_transaction():
    index = load_index()
    rel_extractor = RuleBasedRelationshipExtractor()

    tx_record = {
        "record_type": "transaction",
        "transaction_id": "transaction-00001",
        "from_account_id": "account-00001",
        "to_account_id": "account-00002",
        "amount": "50000",
        "currency": "INR",
        "timestamp": "2024-06-15T10:00:00Z",
    }
    # Need minimal entities to satisfy extract_relationships signature
    from ai.extraction.base import ExtractedEntity
    entities = []
    rels = rel_extractor.extract_relationships(
        entities,
        "",
        structured_records=[tx_record],
    )
    assert len(rels) == 1
    rel = rels[0]
    assert rel.relationship_type == "TRANSFERRED_TO"
    assert rel.source_entity_id == "account-00001"
    assert rel.target_entity_id == "account-00002"
    assert rel.confidence == 1.0
    assert rel.extraction_method == "rule:transferred_to_structured"


def test_spacy_extractor_optional():
    # Should not crash if spaCy unavailable; just report unavailable
    available = is_available()
    if available:
        from ai.extraction import SpacyEntityExtractor
        index = load_index()
        extractor = SpacyEntityExtractor(known_entities=index)
        text = "Rhea Verma works for Bluepeak Traders Ltd."
        entities = extractor.extract(text, source_id="spacy-test")
        assert len(entities) >= 1
        # spaCy should find PERSON and ORG
        types = {e.entity_type for e in entities}
        assert "Person" in types
        assert "Organization" in types
        for e in entities:
            assert e.extraction_method.startswith("spacy:")
    else:
        # spaCy not available; the import should not fail and is_available() == False
        assert available is False


if __name__ == "__main__":
    test_pattern_entity_extractor()
    test_extractor_supports()
    test_relationship_extractor()
    test_structured_relationship_from_transaction()
    test_spacy_extractor_optional()
    print("All extraction tests passed")