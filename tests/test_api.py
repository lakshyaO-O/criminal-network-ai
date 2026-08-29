"""Tests for FastAPI endpoints (Milestone 3)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend-python"))

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    # Use context manager to trigger lifespan startup (loads dataset + graph)
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "criminal-network-analysis"


def test_extract_entities(client):
    payload = {
        "text": "Rhea Verma works for Bluepeak Traders Pvt Ltd. Called +91-901234567.",
        "source_id": "api-test-001",
        "use_spacy": False,
    }
    resp = client.post("/api/extraction/entities", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_id"] == "api-test-001"
    assert data["entity_count"] >= 3
    entities = data["entities"]
    types = {e["entity_type"] for e in entities}
    assert "Person" in types
    assert "Organization" in types
    assert "PhoneNumber" in types
    for e in entities:
        assert e["extraction_method"].startswith("pattern:")


def test_extract_relationships(client):
    payload = {
        "text": "Rhea Verma works for Bluepeak Traders Pvt Ltd. Rhea Verma traveled to Sector 12 Market.",
        "source_id": "api-test-002",
        "entities": [],  # let pipeline extract
        "structured_records": [],
    }
    resp = client.post("/api/extraction/relationships", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_id"] == "api-test-002"
    assert data["relationship_count"] >= 2
    for r in data["relationships"]:
        assert r["extraction_method"].startswith("rule:")
        assert 0.0 <= r["confidence"] <= 1.0


def test_investigation_pipeline(client):
    payload = {
        "text": "Rhea Verma works for Bluepeak Traders Pvt Ltd. Rhea Verma called +91-901234567.",
        "source_id": "api-test-003",
        "use_spacy": False,
        "persist": True,
        "sync_graph": True,
    }
    resp = client.post("/api/investigations/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_id"] == "api-test-003"
    assert data["persisted"]["entities"] > 0
    assert data["persisted"]["relationships"] > 0
    assert data["graph_sync"]["nodes"] > 0
    assert data["graph_sync"]["relationships"] > 0
    # No validation errors expected
    assert data["validation_errors"] == []


def test_get_entity(client):
    # Entity from synthetic dataset
    resp = client.get("/api/entities/person-00001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == "person-00001"
    assert data["entity_type"] == "Person"
    assert "full_name" in data

    # Unknown entity
    resp = client.get("/api/entities/unknown-99999")
    assert resp.status_code == 404


def test_get_entity_relationships(client):
    resp = client.get("/api/entities/person-00001/relationships")
    assert resp.status_code == 200
    data = resp.json()
    assert data["entity_id"] == "person-00001"
    assert isinstance(data["relationships"], list)


def test_get_neighborhood(client):
    resp = client.get("/api/entities/person-00001/neighborhood?depth=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["start_entity_id"] == "person-00001"
    assert data["depth"] == 1
    assert "nodes" in data
    assert "edges" in data

    # Invalid depth
    resp = client.get("/api/entities/person-00001/neighborhood?depth=10")
    assert resp.status_code == 400


def test_get_case(client):
    resp = client.get("/api/cases/case-00001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == "case-00001"
    assert "case_number" in data

    resp = client.get("/api/cases/unknown-99999")
    assert resp.status_code == 404


def test_get_network(client):
    resp = client.get("/api/network/case-00001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == "case-00001"
    assert "entities" in data
    assert "relationships" in data
    assert "statistics" in data

    resp = client.get("/api/network/unknown-99999")
    assert resp.status_code == 404


def test_analysis_global(client):
    resp = client.get("/api/analysis")
    assert resp.status_code == 200
    data = resp.json()
    assert "counts" in data
    assert "indicators" in data
    assert "terminology_notice" in data
    # Verify neutral terminology
    for ind in data["indicators"]:
        assert ind["indicator"] in ("high_network_centrality", "bridge_candidate")
        assert "reason" in ind
        assert "evidence" in ind
    notice_lower = data["terminology_notice"].lower()
    for forbidden in ("guilt probability", "criminal probability", "criminal score", "likely criminal", "criminal detected", "guilt score"):
        assert forbidden not in notice_lower


def test_analysis_case(client):
    resp = client.get("/api/analysis/case-00001")
    assert resp.status_code == 200
    data = resp.json()
    assert "counts" in data
    assert data["counts"]["entities"] > 0


def test_openapi_generation(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["info"]["title"] == "Criminal Network Analysis API"
    paths = spec["paths"]
    # All required endpoints present
    assert "/api/health" in paths
    assert "/api/extraction/entities" in paths
    assert "/api/extraction/relationships" in paths
    assert "/api/investigations/analyze" in paths
    assert "/api/entities/{entity_id}" in paths
    assert "/api/entities/{entity_id}/relationships" in paths
    assert "/api/entities/{entity_id}/neighborhood" in paths
    assert "/api/cases/{case_id}" in paths
    assert "/api/network/{case_id}" in paths
    assert "/api/analysis" in paths


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])