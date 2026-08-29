"""Tests for the investigation pipeline (Milestone 3)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend-python"))

from ai.entity_resolution import DeterministicEntityResolver, EntityIndex
from ai.extraction import PatternEntityExtractor
from ai.pipeline import InvestigationPipeline, InMemoryPersistence
from ai.relationship_rules import RuleBasedRelationshipExtractor
from app.graph import InMemoryGraphRepository

DATA_DIR = Path(__file__).parent.parent / "data" / "synthetic"


def load_index():
    import json
    dataset = {}
    for json_file in DATA_DIR.glob("*.json"):
        if json_file.name.startswith("_"):
            continue
        with json_file.open() as f:
            dataset[json_file.stem] = json.load(f)
    index = EntityIndex.from_dataset(dataset)
    # Deterministic fixtures required for the hard-coded test texts
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


def test_pipeline_end_to_end():
    index = load_index()
    extractor = PatternEntityExtractor(known_entities=index)
    resolver = DeterministicEntityResolver(index)
    rel_extractor = RuleBasedRelationshipExtractor()
    persistence = InMemoryPersistence()
    graph_repo = InMemoryGraphRepository()

    pipeline = InvestigationPipeline(
        extractor=extractor,
        resolver=resolver,
        relationship_extractor=rel_extractor,
        persistence=persistence,
        graph_repository=graph_repo,
    )

    text = (
        "Rhea Verma works for Bluepeak Traders Pvt Ltd. "
        "Rhea Verma called +91-901234567. "
        "Bluepeak Traders Pvt Ltd is located at Sector 12 Market."
    )
    result = pipeline.run(text, source_id="test-001", do_persist=True, do_sync=True)

    assert result.source_id == "test-001"
    assert len(result.entities) > 0
    # Should find Person, Organization, PhoneNumber, Location
    types = {e.entity_type for e in result.entities}
    assert "Person" in types
    assert "Organization" in types
    assert "PhoneNumber" in types
    assert "Location" in types

    # Validation should pass (no errors)
    assert result.validation_errors == []

    # Persistence
    assert result.persisted_entities > 0
    assert result.persisted_relationships > 0

    # Graph sync
    assert result.graph_nodes_upserted > 0
    assert result.graph_relationships_upserted > 0


def test_pipeline_stage_independence():
    """Each stage must be independently callable."""
    index = load_index()
    extractor = PatternEntityExtractor(known_entities=index)
    resolver = DeterministicEntityResolver(index)
    rel_extractor = RuleBasedRelationshipExtractor()

    pipeline = InvestigationPipeline(
        extractor=extractor,
        resolver=resolver,
        relationship_extractor=rel_extractor,
    )

    text = "Rhea Verma works for Bluepeak Traders Pvt Ltd."

    # Stage 1: preprocess
    clean = pipeline.preprocess("  Rhea  Verma   \nworks for  Bluepeak  ")
    assert clean == "Rhea Verma works for Bluepeak"

    # Stage 2: extract entities
    entities = pipeline.extract_entities(text, source_id="test-002")
    assert len(entities) >= 2

    # Stage 3: resolve entities
    resolutions = pipeline.resolve_entities(entities)
    assert isinstance(resolutions, dict)

    # Stage 4: extract relationships
    rels = pipeline.extract_relationships(entities, text, source_id="test-002")
    assert isinstance(rels, list)

    # Stage 5: validate
    from ai.pipeline import PipelineResult
    result = PipelineResult(source_id="test-002")
    result.entities = entities
    result.relationships = rels
    errors = pipeline.validate(result)
    assert isinstance(errors, list)


def test_pipeline_refuses_persist_on_validation_error():
    index = load_index()
    extractor = PatternEntityExtractor(known_entities=index)
    resolver = DeterministicEntityResolver(index)
    rel_extractor = RuleBasedRelationshipExtractor()
    persistence = InMemoryPersistence()

    pipeline = InvestigationPipeline(
        extractor=extractor,
        resolver=resolver,
        relationship_extractor=rel_extractor,
        persistence=persistence,
    )

    # Force a validation error by creating a self-loop relationship
    text = "Rhea Verma knows Rhea Verma."  # co-occurrence would create self-loop if allowed
    result = pipeline.run(text, source_id="test-003", do_persist=False, do_sync=False)

    # Self-loop on same entity text would be caught... manually inject error
    from ai.relationship_rules import RuleRelationship
    result.relationships.append(RuleRelationship(
        relationship_id="rel-00000",
        source_entity_id="person-00001",
        source_type="Person",
        source_text="Rhea Verma",
        target_entity_id="person-00001",
        target_type="Person",
        target_text="Rhea Verma",
        relationship_type="KNOWS",
        confidence=0.5,
        extraction_method="rule:test",
    ))
    pipeline.validate(result)
    assert "self-loop forbidden" in " ".join(result.validation_errors).lower()

    # Persist should raise
    try:
        pipeline.persist(result)
        assert False, "should have raised"
    except ValueError as exc:
        assert "validation errors" in str(exc).lower()


if __name__ == "__main__":
    test_pipeline_end_to_end()
    test_pipeline_stage_independence()
    test_pipeline_refuses_persist_on_validation_error()
    print("All pipeline tests passed")