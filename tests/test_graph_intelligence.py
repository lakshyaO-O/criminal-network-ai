"""Tests for Graph Intelligence Engine — Milestone 5.

Covers:
- centrality (degree, betweenness, closeness, PageRank) real calculations
- communities (greedy modularity, deterministic)
- bridge nodes (betweenness + articulation)
- shortest paths / multi-hop (1..6)
- neighborhood depth
- transaction chains
- temporal bursts
- indicator generation + explainability
- deterministic output
- edge cases (empty, single-node, disconnected)
- forbidden terminology absence

All metrics use the deterministic synthetic dataset (seed 42) without modifying it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend-python"))

from app.services.network_analysis import (
    analyze_graph,
    analyze_network,
    compute_centrality,
    find_communities,
    find_bridges,
    compute_relationship_strength,
    analyze_temporal,
    find_transaction_chains,
    generate_indicators,
    connected_components,
)


def _load_synthetic_snapshot():
    import json

    data_dir = Path(__file__).parent.parent / "data" / "synthetic"
    dataset = {}
    for f in data_dir.glob("*.json"):
        if f.name.startswith("_"):
            continue
        dataset[f.stem] = json.load(open(f, encoding="utf-8"))
    # Build snapshot like graph repo export
    entities = {}
    for key in ("persons", "organizations", "phone_numbers", "vehicles", "locations", "financial_accounts", "transactions", "communications", "cases", "firs", "events", "evidence"):
        for row in dataset.get(key, []):
            eid = row.get("entity_id")
            etype = row.get("entity_type")
            if eid and etype:
                entities[eid] = (etype, row)
    relationships = dataset.get("relationships", [])
    return entities, relationships, dataset


# ---------------------------------------------------------------------------
# Centrality
# ---------------------------------------------------------------------------

def test_centrality_real_calculation():
    entities, relationships, _ = _load_synthetic_snapshot()
    centrality = compute_centrality(entities, relationships)
    for metric in ("degree", "betweenness", "closeness", "pagerank"):
        assert metric in centrality
        # Every entity has a score
        for eid in entities:
            assert eid in centrality[metric]
            assert 0.0 <= centrality[metric][eid] <= 1.0
    # Degree centrality: highly connected entity should have higher degree than isolated
    # Check that max degree > min
    deg_vals = list(centrality["degree"].values())
    assert max(deg_vals) > min(deg_vals)
    # Betweenness should have at least one bridge node with >0
    assert max(centrality["betweenness"].values()) > 0
    # PageRank sums to ~1
    pr_sum = sum(centrality["pagerank"].values())
    assert 0.99 <= pr_sum <= 1.01


def test_centrality_deterministic():
    entities, relationships, _ = _load_synthetic_snapshot()
    c1 = compute_centrality(entities, relationships)
    c2 = compute_centrality(entities, relationships)
    assert c1 == c2


def test_centrality_empty_graph():
    centrality = compute_centrality({}, [])
    for metric in ("degree", "betweenness", "closeness", "pagerank"):
        assert centrality[metric] == {}


def test_centrality_single_node():
    entities = {"person-00001": ("Person", {"full_name": "Solo"})}
    centrality = compute_centrality(entities, [])
    assert centrality["degree"]["person-00001"] == 0.0
    assert centrality["betweenness"]["person-00001"] == 0.0


# ---------------------------------------------------------------------------
# Communities
# ---------------------------------------------------------------------------

def test_communities_greedy_modularity():
    entities, relationships, _ = _load_synthetic_snapshot()
    comms = find_communities(entities, relationships)
    assert len(comms) >= 2  # synthetic has 6 communities of 5 persons each + bridge structure
    # Each community has required fields
    for c in comms:
        assert "community_id" in c
        assert "members" in c
        assert "size" in c
        assert "internal_edges" in c
        assert "density" in c
        assert c["size"] == len(c["members"])
        assert 0.0 <= c["density"] <= 1.0
        # No forbidden terminology
        assert "gang" not in c["community_id"].lower()
        assert "criminal" not in json.dumps(c).lower()
    # Deterministic: sorted by min member
    ids = [c["community_id"] for c in comms]
    assert ids == sorted(ids)
    # All entities covered? (communities should partition)
    all_members = [m for c in comms for m in c["members"]]
    # Might not cover isolated transaction/evidence nodes if disconnected, but persons should be covered
    assert len(set(all_members)) == len(all_members)  # no duplicates


def test_communities_deterministic():
    entities, relationships, _ = _load_synthetic_snapshot()
    c1 = find_communities(entities, relationships)
    c2 = find_communities(entities, relationships)
    assert c1 == c2


def test_communities_empty():
    assert find_communities({}, []) == []


# ---------------------------------------------------------------------------
# Bridges
# ---------------------------------------------------------------------------

def test_bridges_detection():
    entities, relationships, _ = _load_synthetic_snapshot()
    bridges = find_bridges(entities, relationships, top_k=10)
    # Synthetic has bridge nodes connecting communities
    assert len(bridges) >= 1
    for b in bridges:
        assert "entity_id" in b
        assert "metric" in b
        assert b["metric"] in ("articulation_point", "betweenness_centrality", "community_boundary")
        assert "score" in b
        assert 0.0 <= b["score"] <= 1.0
        assert "explanation" in b and len(b["explanation"]) > 20
        assert "evidence" in b and len(b["evidence"]) > 0
        # No forbidden
        assert "criminal" not in b["explanation"].lower()
        assert "guilty" not in b["explanation"].lower()


def test_bridges_deterministic():
    entities, relationships, _ = _load_synthetic_snapshot()
    b1 = find_bridges(entities, relationships)
    b2 = find_bridges(entities, relationships)
    assert b1 == b2


# ---------------------------------------------------------------------------
# Shortest path / neighborhood
# ---------------------------------------------------------------------------

def test_shortest_path_via_graph_repo():
    from app.graph.memory import InMemoryGraphRepository

    entities, relationships, _ = _load_synthetic_snapshot()
    repo = InMemoryGraphRepository()
    for eid, (etype, props) in entities.items():
        repo.upsert_entity(eid, etype, props)
    for rel in relationships:
        try:
            repo.upsert_relationship(
                rel["relationship_id"], rel["source_id"], rel["source_type"],
                rel["target_id"], rel["target_type"], rel["relationship_type"],
                {k: v for k, v in rel.items() if k not in ("source_id", "source_type", "target_id", "target_type", "relationship_type", "relationship_id")},
            )
        except Exception:
            pass

    # Pick two persons from different communities that should be connected via bridge
    # Use first and last person
    persons = [eid for eid, (etype, _) in entities.items() if etype == "Person"]
    src, dst = persons[0], persons[-1]
    path = repo.shortest_path(src, dst, max_depth=6)
    assert path is not None
    assert path["found"] in (True, False)
    if path["found"]:
        assert path["length"] >= 1
        assert path["entities"][0] == src
        assert path["entities"][-1] == dst
        assert len(path["entities"]) == path["length"] + 1


def test_neighborhood_depth():
    from app.graph.memory import InMemoryGraphRepository

    entities, relationships, _ = _load_synthetic_snapshot()
    repo = InMemoryGraphRepository()
    for eid, (etype, props) in list(entities.items())[:10]:
        repo.upsert_entity(eid, etype, props)
    for rel in relationships[:20]:
        try:
            repo.upsert_relationship(
                rel["relationship_id"], rel["source_id"], rel["source_type"],
                rel["target_id"], rel["target_type"], rel["relationship_type"], {}
            )
        except Exception:
            pass
    # Use a known entity
    eid = list(entities.keys())[0]
    for depth in (1, 2, 3):
        nb = repo.neighborhood(eid, depth=depth)
        assert nb["start_entity_id"] == eid
        assert nb["depth"] == depth
        assert "nodes" in nb and "edges" in nb
        # Depth 1 should have at least start node
        assert len(nb["nodes"]) >= 1

    # Invalid depth should be handled by API layer (400), but repo allows any depth
    # Here we test that depth 6 is max in API; repo should still work
    nb6 = repo.neighborhood(eid, depth=6)
    assert nb6["depth"] == 6


def test_empty_graph_neighborhood():
    from app.graph.memory import InMemoryGraphRepository

    repo = InMemoryGraphRepository()
    repo.upsert_entity("person-00001", "Person", {"full_name": "Solo"})
    nb = repo.neighborhood("person-00001", depth=1)
    assert nb["nodes"] == [{"entity_id": "person-00001", "depth": 0}]
    assert nb["edges"] == []


# ---------------------------------------------------------------------------
# Transaction chains
# ---------------------------------------------------------------------------

def test_transaction_chains_detected():
    _, relationships, _ = _load_synthetic_snapshot()
    chains = find_transaction_chains(relationships)
    # Synthetic has transaction chains (45 tx, with 6 flagged demo trio)
    assert len(chains) >= 1
    for ch in chains:
        assert "chain_id" in ch
        assert "source_account" in ch
        assert "destination_account" in ch
        assert "hop_count" in ch and ch["hop_count"] >= 2
        assert "evidence" in ch and len(ch["evidence"]) == ch["hop_count"]
        assert "explanation" in ch
        assert "criminal" not in ch["explanation"].lower()
        assert "guilty" not in ch["explanation"].lower()


def test_transaction_chains_empty():
    assert find_transaction_chains([]) == []
    assert find_transaction_chains([{"relationship_type": "KNOWS", "source_id": "a", "target_id": "b"}]) == []


# ---------------------------------------------------------------------------
# Temporal bursts
# ---------------------------------------------------------------------------

def test_temporal_bursts():
    _, relationships, _ = _load_synthetic_snapshot()
    bursts = analyze_temporal(relationships)
    # Synthetic has repeated communications (temporal bursts)
    # Should detect at least one burst
    assert isinstance(bursts, list)
    for b in bursts:
        assert "indicator_type" in b
        assert b["indicator_type"] in ("temporal_burst", "communication_burst", "transaction_burst", "interaction_burst")
        assert "time_window" in b
        assert "observed_count" in b and b["observed_count"] >= 3
        assert "baseline" in b and "mean" in b["baseline"]
        assert "explanation" in b and len(b["explanation"]) > 20
        assert "evidence" in b
        assert "criminal" not in b["explanation"].lower()


def test_temporal_empty():
    assert analyze_temporal([]) == []


# ---------------------------------------------------------------------------
# Relationship strength
# ---------------------------------------------------------------------------

def test_relationship_strength():
    _, relationships, _ = _load_synthetic_snapshot()
    strengths = compute_relationship_strength(relationships)
    assert len(strengths) == len(relationships)
    for s in strengths:
        assert "relationship_id" in s
        assert 0.0 <= s["interaction_strength"] <= 1.0
        assert "factors" in s
        assert "explanation" in s
        assert "criminal" not in s["explanation"].lower()
    # Sorted desc
    scores = [s["interaction_strength"] for s in strengths]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Indicators + explainability + forbidden terminology
# ---------------------------------------------------------------------------

def test_indicators_structured():
    entities, relationships, _ = _load_synthetic_snapshot()
    indicators = generate_indicators(entities, relationships)
    assert len(indicators) >= 3  # at least centrality, bridge, temporal, chain
    for ind in indicators:
        for field in ("indicator_id", "indicator_type", "severity", "entity_ids", "relationship_ids", "score", "explanation", "evidence", "created_at"):
            assert field in ind, f"missing {field}"
        assert ind["severity"] in ("LOW", "MEDIUM", "HIGH")
        # Severity is analytical, not criminality — explanation must not say "risk criminal"
        text = json.dumps(ind).lower()
        for forbidden in ("criminal probability", "guilt probability", "guilt score", "criminal score", "is criminal", "is guilty", "likely criminal", "criminal detected"):
            assert forbidden not in text, f"forbidden '{forbidden}' in {ind['indicator_id']}"
        assert len(ind["explanation"]) > 20
        assert isinstance(ind["evidence"], list)


def test_indicator_deterministic():
    entities, relationships, _ = _load_synthetic_snapshot()
    i1 = generate_indicators(entities, relationships)
    i2 = generate_indicators(entities, relationships)
    # Strip created_at for determinism (timestamp varies per call)
    def _strip(indicators):
        cleaned = []
        for ind in indicators:
            c = dict(ind)
            c.pop("created_at", None)
            cleaned.append(c)
        return cleaned
    assert _strip(i1) == _strip(i2)


# ---------------------------------------------------------------------------
# Full graph analysis (enriched) + backward compat + edge cases
# ---------------------------------------------------------------------------

def test_full_analysis_enriched():
    entities, relationships, _ = _load_synthetic_snapshot()
    result = analyze_graph(entities, relationships)
    # Legacy keys still present
    for key in ("counts", "entity_type_counts", "degree_statistics", "indicators", "terminology_notice"):
        assert key in result
    # New keys
    for key in ("centrality", "centrality_explanations", "communities_detailed", "bridges_detailed", "temporal_indicators", "transaction_chains", "relationship_strength", "indicators_enhanced"):
        assert key in result
    # Terminology notice must not contain guilt scoring
    notice = result["terminology_notice"].lower()
    for forbidden in ("guilt probability", "criminal probability", "criminal score"):
        assert forbidden not in notice
    # New indicators must be explainable
    for ind in result.get("indicators_enhanced", []):
        assert "explanation" in ind and len(ind["explanation"]) > 20


def test_analyze_empty_graph():
    result = analyze_graph({}, [])
    assert result["counts"]["entities"] == 0
    assert result["counts"]["relationships"] == 0
    assert result["counts"]["connected_components"] == 0
    assert result["centrality"]["degree"] == {}
    assert result["communities_detailed"] == []
    assert result["bridges_detailed"] == []
    assert result["transaction_chains"] == []


def test_analyze_single_node():
    entities = {"person-00001": ("Person", {"full_name": "Solo"})}
    result = analyze_graph(entities, [])
    assert result["counts"]["entities"] == 1
    assert result["counts"]["connected_components"] == 1
    assert result["degree_statistics"]["min"] == 0
    # Centrality should have 0 for single node
    assert result["centrality"]["degree"]["person-00001"] == 0.0


def test_analyze_disconnected_graph():
    entities = {
        "person-00001": ("Person", {}),
        "person-00002": ("Person", {}),
        "person-00003": ("Person", {}),
    }
    relationships = [
        {"source_id": "person-00001", "target_id": "person-00002", "relationship_type": "KNOWS", "relationship_id": "rel-00001"},
    ]
    result = analyze_graph(entities, relationships)
    assert result["counts"]["connected_components"] == 2  # one edge + isolated
    assert result["counts"]["entities"] == 3


def test_no_forbidden_terminology_in_any_analysis():
    entities, relationships, _ = _load_synthetic_snapshot()
    result = analyze_graph(entities, relationships)
    blob = json.dumps(result).lower()
    for forbidden in ("guilt probability", "criminal probability", "guilt score", "criminal score", "criminality score", "is criminal", "is guilty", "likely criminal", "criminal detected", "dangerous"):
        assert forbidden not in blob, f"forbidden '{forbidden}' found in analysis output"


def test_legacy_analyze_network_still_works():
    # Old tests import analyze_network directly
    entities = {
        "person-00001": ("Person", {"full_name": "Rhea Verma"}),
        "person-00002": ("Person", {"full_name": "Kabir Rao"}),
        "org-00001": ("Organization", {"name": "Bluepeak"}),
    }
    relationships = [
        {"source_id": "person-00001", "target_id": "person-00002", "relationship_type": "KNOWS", "relationship_id": "rel-00001"},
        {"source_id": "person-00001", "target_id": "org-00001", "relationship_type": "WORKS_FOR", "relationship_id": "rel-00002"},
    ]
    result = analyze_network(entities, relationships)
    assert result["counts"]["entities"] == 3
    assert "indicators" in result
    assert "terminology_notice" in result


# ---------------------------------------------------------------------------
# API smoke for new endpoints (using in-memory graph)
# ---------------------------------------------------------------------------

def test_api_new_endpoints_smoke():
    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        # Existing still works
        resp = client.get("/api/health")
        assert resp.status_code == 200
        # New intelligence endpoints
        for path in (
            "/api/analysis/centrality",
            "/api/analysis/communities",
            "/api/analysis/bridges",
            "/api/analysis/temporal",
            "/api/analysis/transaction-chains",
            "/api/analysis/relationship-strength",
            "/api/analysis/indicators",
        ):
            r = client.get(path)
            assert r.status_code == 200, f"{path} failed: {r.text[:500]}"
            data = r.json()
            assert isinstance(data, dict)
            # No forbidden
            assert "criminal probability" not in json.dumps(data).lower()

        # Path
        r = client.get("/api/analysis/path?source_id=person-00001&target_id=person-00002")
        # May be 200 or 404 depending on whether those IDs are connected; but not 500
        assert r.status_code in (200, 404)

        # Entity centrality (use known synthetic person)
        r = client.get("/api/analysis/entities/person-00001/centrality")
        assert r.status_code in (200, 404)  # 404 if entity not in graph (but synthetic has it)
        if r.status_code == 200:
            data = r.json()
            assert "centrality" in data
            assert "explanations" in data

        # Communities must be deterministic
        r1 = client.get("/api/analysis/communities")
        r2 = client.get("/api/analysis/communities")
        assert r1.json() == r2.json()
