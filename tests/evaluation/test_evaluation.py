import pytest
from ai.evaluation.metrics import compute_prf, entity_metrics, relationship_metrics
from ai.grounding import validate_analysis_grounding

def test_compute_prf():
    r = compute_prf(2, 1, 1)
    assert abs(r["precision"] - 0.666) < 0.01
    assert abs(r["recall"] - 0.666) < 0.01

def test_entity_metrics():
    exp = [{"canonical_type": "Person", "value": "Rhea Verma"}, {"canonical_type": "Organization", "value": "Bluepeak"}]
    pred = [{"canonical_type": "Person", "value": "Rhea Verma"}]
    m = entity_metrics(exp, pred)
    assert m["tp"] == 1 and m["fn"] == 1 and m["fp"] == 0

def test_relationship_metrics():
    exp = [{"source": "A", "target": "B", "relationship_type": "WORKS_FOR"}]
    pred = [{"source": "A", "target": "B", "relationship_type": "WORKS_FOR"}]
    m = relationship_metrics(exp, pred)
    assert m["precision"] == 1.0

def test_grounding_validator():
    snap = {"entities": {"person-00001": ["Person", {}]}, "relationships": [{"relationship_id": "rel-00001", "source_id": "person-00001", "target_id": "person-00002", "relationship_type": "KNOWS"}]}
    analysis = {"supporting_entity_ids": ["person-00001"], "supporting_relationship_ids": ["rel-00001"], "supporting_evidence_ids": [], "observations": ["Observed 1 entities"], "analytical_interpretation": [], "summary": "test"}
    res = validate_analysis_grounding(analysis, snap)
    assert res["overall_status"] == "SUPPORTED"
    analysis2 = {"supporting_entity_ids": ["person-99999"], "supporting_relationship_ids": [], "supporting_evidence_ids": [], "observations": [], "analytical_interpretation": [], "summary": ""}
    res2 = validate_analysis_grounding(analysis2, snap)
    assert res2["overall_status"] == "NEEDS_REVIEW"
    assert res2["checks"]["entities"]["unsupported"] == ["person-99999"]

def test_evaluation_dataset_exists():
    import json, pathlib
    p = pathlib.Path("tests/fixtures/ai/scenarios.json")
    assert p.exists()
    data = json.loads(p.read_text())
    assert len(data["scenarios"]) >= 8
    for scen in data["scenarios"]:
        assert "text" in scen and "expected_entities" in scen
