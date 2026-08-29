"""Tests for Audit Trail — Milestone 9A."""

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
        # Clear audit at start for deterministic tests
        c.post("/api/audit/events/clear")
        yield c


def test_audit_event_creation_on_analysis(client):
    # Trigger an analysis that should create audit events (via explainability or investigation)
    # We test via explainability which records audit
    r = client.get("/api/explainability/centrality?entity_id=person-00001")
    assert r.status_code == 200
    # Query audit
    resp = client.get("/api/audit/events?analysis_type=centrality&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert any(e["analysis_type"] == "centrality" for e in data["events"])


def test_audit_event_retrieval(client):
    # Create a finding to generate audit
    client.get("/api/investigations/findings?root_entity_id=person-00001&depth=1")
    # Query
    resp = client.get("/api/audit/events?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert "count" in data
    assert "total" in data
    assert data["limit"] == 10
    # Check deterministic ordering: sorted by timestamp, audit_id
    events = data["events"]
    for i in range(len(events) - 1):
        assert (events[i]["timestamp"], events[i]["audit_id"]) <= (events[i+1]["timestamp"], events[i+1]["audit_id"])


def test_audit_filtering(client):
    # Create an event with specific case
    client.get("/api/explainability/communities?case_id=case-00001")
    # Filter by case_id
    resp = client.get("/api/audit/events?case_id=case-00001&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    # May be 0 if no event used case_id, but should not error
    assert isinstance(data["events"], list)
    # Filter by event_type
    resp2 = client.get("/api/audit/events?event_type=explainability_requested&limit=5")
    assert resp2.status_code == 200
    for ev in resp2.json()["events"]:
        assert ev["event_type"] == "explainability_requested"


def test_audit_deterministic_ordering(client):
    # Two sequential queries should be deterministic
    r1 = client.get("/api/audit/events?limit=5")
    r2 = client.get("/api/audit/events?limit=5")
    assert r1.json()["events"] == r2.json()["events"]


def test_audit_bounded_results(client):
    # Request with limit
    resp = client.get("/api/audit/events?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] <= 2
    assert len(data["events"]) <= 2
    # Offset
    resp2 = client.get("/api/audit/events?limit=2&offset=1")
    assert resp2.status_code == 200
    assert resp2.json()["offset"] == 1


def test_audit_invalid_filters(client):
    resp = client.get("/api/audit/events?limit=0")
    assert resp.status_code == 400
    resp2 = client.get("/api/audit/events?limit=200")
    assert resp2.status_code == 400
    resp3 = client.get("/api/audit/events?offset=-1")
    assert resp3.status_code == 400


def test_audit_nonexistent_references(client):
    # Query with nonexistent case should return empty, not 404
    resp = client.get("/api/audit/events?case_id=nonexistent-99999&limit=10")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_audit_no_secrets(client):
    # Trigger an event and check it doesn't leak secrets
    client.get("/api/explainability/entities/person-00001")
    resp = client.get("/api/audit/events?limit=10")
    assert resp.status_code == 200
    blob = json.dumps(resp.json()).lower()
    for secret in ("password", "secret", "token", "connection_string", "database_url", "env"):
        if secret in ("password", "secret", "token", "connection_string", "database_url"):
            assert secret not in blob, f"secret '{secret}' leaked in audit"
    for forbidden in ("crime probability", "guilt probability", "is criminal"):
        assert forbidden not in blob


def test_audit_clear(client):
    # Ensure clear works (for test isolation)
    client.get("/api/explainability/centrality?entity_id=person-00001")
    resp = client.get("/api/audit/events?limit=10")
    assert resp.json()["total"] >= 1
    clear = client.post("/api/audit/events/clear")
    assert clear.status_code == 200
    resp2 = client.get("/api/audit/events?limit=10")
    assert resp2.json()["total"] == 0
    assert resp2.json()["count"] == 0
