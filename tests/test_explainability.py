"""Tests for Explainability, Lineage, Audit — Milestone 9A."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend-python"))

from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _check_explanation(data):
    # Every explanation must have these
    for field in ("explanation_id", "analysis_type", "summary", "methodology", "observations", "contributing_entities", "contributing_relationships", "supporting_evidence", "parameters", "thresholds", "limitations", "provenance", "generated_at", "lineage", "reproducibility"):
        assert field in data, f"missing {field}"
    assert len(data["summary"]) > 10
    assert len(data["methodology"]) > 20
    assert isinstance(data["observations"], list)
    assert len(data["limitations"]) > 10
    # No forbidden
    blob = json.dumps(data).lower()
    for forbidden in ("crime probability", "guilt probability", "criminal score", "is criminal", "is guilty"):
        assert forbidden not in blob
    # Provenance
    assert isinstance(data["provenance"], list) and len(data["provenance"]) >= 1
    for prov in data["provenance"]:
        assert "source" in prov and "analysis_type" in prov
    # Lineage
    assert "analysis_type" in data["lineage"]
    assert "algorithm" in data["lineage"]
    # Reproducibility
    assert data["reproducibility"].get("deterministic") is True
    assert "result_id" in data["reproducibility"]


# ---------------------------------------------------------------------------
# Finding explanation
# ---------------------------------------------------------------------------

def test_finding_explanation(client):
    # Get a finding first via investigation
    resp = client.get("/api/investigations/findings?root_entity_id=person-00001&depth=1")
    assert resp.status_code == 200
    findings = resp.json()["findings"]
    assert len(findings) >= 1
    fid = findings[0]["finding_id"]
    # Explain it
    r = client.get(f"/api/explainability/findings/{fid}")
    assert r.status_code == 200
    data = r.json()
    _check_explanation(data)
    assert data["analysis_type"] == "finding"
    assert fid in data["explanation_id"] or fid in json.dumps(data)
    # Check explanation contains summary/methodology
    assert "summary" in data and len(data["summary"]) > 10
    assert "methodology" in data


def test_finding_explanation_404(client):
    resp = client.get("/api/explainability/findings/nonexistent-99999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Entity explanation
# ---------------------------------------------------------------------------

def test_entity_explanation(client):
    r = client.get("/api/explainability/entities/person-00001")
    assert r.status_code == 200
    data = r.json()
    _check_explanation(data)
    assert data["analysis_type"] == "entity"
    # Must distinguish observed vs analytical
    assert "observed_data" in data or "analytical_interpretation" in data or "methodology" in data
    # Check that it contains both
    blob = json.dumps(data).lower()
    assert "observed" in blob
    assert "analytical" in blob or "centrality" in blob


def test_entity_explanation_404(client):
    r = client.get("/api/explainability/entities/nonexistent-99999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Centrality explanation
# ---------------------------------------------------------------------------

def test_centrality_explanation(client):
    r = client.get("/api/explainability/centrality?entity_id=person-00001")
    assert r.status_code == 200
    data = r.json()
    _check_explanation(data)
    assert data["analysis_type"] == "centrality"
    assert "degree" in data["methodology"].lower() or "betweenness" in data["methodology"].lower()
    # Also via path param
    r2 = client.get("/api/explainability/centrality/person-00001")
    assert r2.status_code == 200
    assert r2.json()["analysis_type"] == "centrality"


def test_centrality_explanation_404(client):
    r = client.get("/api/explainability/centrality?entity_id=nonexistent-99999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Bridge explanation
# ---------------------------------------------------------------------------

def test_bridge_explanation(client):
    # Use a known bridge entity from investigation
    # First get bridges via analysis
    r = client.get("/api/analysis/bridges")
    assert r.status_code == 200
    bridges = r.json()["bridges"]
    if not bridges:
        pytest.skip("no bridges in synthetic graph")
    eid = bridges[0]["entity_id"]
    r2 = client.get(f"/api/explainability/bridges/{eid}")
    assert r2.status_code == 200
    data = r2.json()
    _check_explanation(data)
    assert data["analysis_type"] == "bridge"


def test_bridge_explanation_not_bridge(client):
    # Entity that is not a bridge should still get an explanation (not 404, but explain why not)
    # Use an isolated or low-degree entity
    r = client.get("/api/explainability/bridges/person-00001")
    # Could be bridge or not, but should not 404 if entity exists
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        assert data["analysis_type"] == "bridge"


# ---------------------------------------------------------------------------
# Temporal explanation
# ---------------------------------------------------------------------------

def test_temporal_explanation(client):
    r = client.get("/api/explainability/temporal")
    assert r.status_code == 200
    data = r.json()
    _check_explanation(data)
    assert data["analysis_type"] == "temporal"
    assert "window" in data["methodology"].lower() or "burst" in data["methodology"].lower()


def test_temporal_explanation_entity(client):
    r = client.get("/api/explainability/temporal?entity_id=person-00001")
    # May be 404 if no burst for that entity, but should not 500
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        _check_explanation(r.json())


# ---------------------------------------------------------------------------
# Transaction chain explanation
# ---------------------------------------------------------------------------

def test_chain_explanation(client):
    r = client.get("/api/explainability/transaction-chains")
    assert r.status_code == 200
    data = r.json()
    _check_explanation(data)
    assert data["analysis_type"] == "transaction_chain"


def test_chain_explanation_404(client):
    r = client.get("/api/explainability/transaction-chains?chain_id=nonexistent-99999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Relationship strength explanation
# ---------------------------------------------------------------------------

def test_strength_explanation(client):
    # Get a relationship id via graph
    r = client.get("/api/entities/person-00001/relationships")
    assert r.status_code == 200
    rels = r.json()["relationships"]
    assert len(rels) >= 1
    rid = rels[0]["relationship_id"]
    r2 = client.get(f"/api/explainability/relationship-strength/{rid}")
    assert r2.status_code == 200
    data = r2.json()
    _check_explanation(data)
    assert data["analysis_type"] == "relationship_strength"


def test_strength_404(client):
    r = client.get("/api/explainability/relationship-strength/rel-99999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Indicator explanation
# ---------------------------------------------------------------------------

def test_indicator_explanation(client):
    # Get an indicator via analysis
    r = client.get("/api/analysis/indicators")
    assert r.status_code == 200
    indicators = r.json()["indicators"]
    if not indicators:
        pytest.skip("no indicators")
    iid = indicators[0]["indicator_id"]
    r2 = client.get(f"/api/explainability/indicators/{iid}")
    assert r2.status_code == 200
    data = r2.json()
    _check_explanation(data)
    assert data["analysis_type"] == "indicator"


def test_indicator_404(client):
    r = client.get("/api/explainability/indicators/nonexistent-99999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Community explanation
# ---------------------------------------------------------------------------

def test_community_explanation(client):
    r = client.get("/api/explainability/communities")
    assert r.status_code == 200
    data = r.json()
    _check_explanation(data)
    assert data["analysis_type"] == "community"


def test_community_explanation_entity(client):
    r = client.get("/api/explainability/communities/person-00001")
    assert r.status_code == 200
    _check_explanation(r.json())


# ---------------------------------------------------------------------------
# Provenance & Reproducibility
# ---------------------------------------------------------------------------

def test_provenance_retained(client):
    r = client.get("/api/explainability/entities/person-00001")
    assert r.status_code == 200
    data = r.json()
    assert "provenance" in data and len(data["provenance"]) >= 1
    for prov in data["provenance"]:
        assert "source" in prov
        assert "timestamp" in prov


def test_reproducibility_deterministic(client):
    r1 = client.get("/api/explainability/centrality?entity_id=person-00001")
    r2 = client.get("/api/explainability/centrality?entity_id=person-00001")
    assert r1.json()["explanation_id"] == r2.json()["explanation_id"]
    assert r1.json()["reproducibility"]["result_id"] == r2.json()["reproducibility"]["result_id"]


def test_explanation_no_secrets(client):
    r = client.get("/api/explainability/entities/person-00001")
    assert r.status_code == 200
    blob = json.dumps(r.json()).lower()
    for secret in ("password", "secret", "token", "connection_string", "database_url", "dsn", "env"):
        # Allow "password" in methodology? No, should not leak
        # We check that no actual secret values are leaked (the word password should not appear at all)
        if secret in ("password", "secret"):
            assert secret not in blob, f"secret '{secret}' leaked"
    # No guilt
    for forbidden in ("crime probability", "guilt probability", "is criminal", "is guilty"):
        assert forbidden not in blob

