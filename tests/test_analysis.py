"""Tests for network analysis service (Milestone 3)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend-python"))

from app.services.network_analysis import (
    analyze_network,
    connected_components,
    label_propagation_communities,
    articulation_points,
)


def make_snapshot():
    entities = {
        "person-00001": ("Person", {"full_name": "Rhea Verma"}),
        "person-00002": ("Person", {"full_name": "Kabir Rao"}),
        "person-00003": ("Person", {"full_name": "Aarav Sharma"}),
        "org-00001": ("Organization", {"name": "Bluepeak Traders"}),
    }
    relationships = [
        {"source_id": "person-00001", "target_id": "person-00002",
         "relationship_type": "KNOWS", "relationship_id": "rel-00001"},
        {"source_id": "person-00001", "target_id": "org-00001",
         "relationship_type": "WORKS_FOR", "relationship_id": "rel-00002"},
        {"source_id": "person-00002", "target_id": "person-00003",
         "relationship_type": "KNOWS", "relationship_id": "rel-00003"},
    ]
    return entities, relationships


def test_analyze_network_basic():
    entities, relationships = make_snapshot()
    result = analyze_network(entities, relationships, top_k=5)

    assert result["counts"]["entities"] == 4
    assert result["counts"]["relationships"] == 3
    assert result["counts"]["connected_components"] == 1
    assert result["counts"]["communities_detected"] >= 1

    # Degree stats
    ds = result["degree_statistics"]
    assert ds["min"] >= 1
    assert ds["max"] >= 2
    assert ds["average"] > 0

    # Indicators
    indicators = result["indicators"]
    # Should have high_network_centrality for person-00001 (degree 2)
    high_centrality = [i for i in indicators if i["indicator"] == "high_network_centrality"]
    assert len(high_centrality) >= 1
    for ind in high_centrality:
        assert ind["entity_id"] in entities
        assert "reason" in ind and len(ind["reason"]) > 0
        assert "evidence" in ind and len(ind["evidence"]) > 0

    # Bridge candidate for person-00001 (articulation point)
    bridges = [i for i in indicators if i["indicator"] == "bridge_candidate"]
    assert len(bridges) >= 1
    for ind in bridges:
        assert "reason" in ind
        assert "evidence" in ind

    # Terminology notice — must be descriptive and not assign verdicts.
    # The notice may mention that guilt/criminality are NOT assessed, but it must not contain verdict phrases.
    assert "terminology_notice" in result
    notice_lower = result["terminology_notice"].lower()
    for forbidden in ("guilt probability", "criminal probability", "criminal score", "likely criminal", "criminal detected", "guilt score"):
        assert forbidden not in notice_lower, f"forbidden phrase '{forbidden}' in terminology_notice"
    # Must explicitly state descriptive nature
    assert "descriptive" in notice_lower or "human review" in notice_lower


def test_connected_components():
    entities, relationships = make_snapshot()
    from app.services.network_analysis import _adjacency
    adj = _adjacency(entities, relationships)
    comps = connected_components(adj)
    assert len(comps) == 1
    assert set(comps[0]) == set(entities.keys())

    # Add isolated entity
    entities2 = {**entities, "person-99999": ("Person", {"full_name": "Isolated"})}
    adj2 = _adjacency(entities2, relationships)
    comps2 = connected_components(adj2)
    assert len(comps2) == 2
    assert "person-99999" in comps2[0] or "person-99999" in comps2[1]


def test_label_propagation_communities():
    entities, relationships = make_snapshot()
    from app.services.network_analysis import _adjacency
    adj = _adjacency(entities, relationships)
    communities = label_propagation_communities(adj)
    assert len(communities) >= 1
    total = sum(len(c) for c in communities)
    assert total == len(entities)


def test_articulation_points():
    entities, relationships = make_snapshot()
    from app.services.network_analysis import _adjacency
    adj = _adjacency(entities, relationships)
    points = articulation_points(adj)
    assert "person-00001" in points  # removing disconnects person-00003
    assert "person-00002" in points  # removing disconnects person-00003


def test_disconnected_graph_analysis():
    entities = {
        "p1": ("Person", {}),
        "p2": ("Person", {}),
        "p3": ("Person", {}),
    }
    relationships = [
        {"source_id": "p1", "target_id": "p2",
         "relationship_type": "KNOWS", "relationship_id": "r1"},
        # p3 isolated
    ]
    result = analyze_network(entities, relationships, top_k=5)
    assert result["counts"]["connected_components"] == 2
    assert result["counts"]["entities"] == 3


if __name__ == "__main__":
    test_analyze_network_basic()
    test_connected_components()
    test_label_propagation_communities()
    test_articulation_points()
    test_disconnected_graph_analysis()
    print("All analysis tests passed")