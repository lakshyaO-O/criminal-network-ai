"""Investigation Engine — Milestone 8A.

Deterministic, explainable, provenance-aware investigation workspace.

Provides:
- subgraph extraction (case + root + N-hop + filters, bounded)
- multi-hop path investigator representation
- evidence aggregation
- candidate finding generation (from existing intelligence)
- snapshot representation

All outputs are neutral investigative terminology, never guilt/criminality.
Every finding retains provenance (source entity/relationship, analysis type, timestamp).

Limits are explicit and deterministic.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.graph.base import GraphRepository
from app.services.network_analysis import (
    compute_centrality,
    find_bridges,
    find_communities,
    analyze_temporal,
    find_transaction_chains,
    compute_relationship_strength,
    generate_indicators,
)


# ---------------------------------------------------------------------------
# Constants (also in schemas, duplicated for service independence)
# ---------------------------------------------------------------------------

MAX_DEPTH = 6
MAX_NODES = 200
MAX_RELATIONSHIPS = 400
MAX_PATHS = 20
MAX_FINDINGS = 20

# Deterministic generation time for snapshots/findings (not wall-clock per call)
FIXED_GENERATED_AT = "2024-01-01T00:00:00Z"


def _now_iso() -> str:
    # Deterministic for tests; use fixed time
    return FIXED_GENERATED_AT


def _hash_id(*parts: str) -> str:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]
    return h


# ---------------------------------------------------------------------------
# Subgraph
# ---------------------------------------------------------------------------

def investigation_subgraph(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    root_entity_id: str,
    depth: int = 1,
    case_id: Optional[str] = None,
    entity_types: Optional[List[str]] = None,
    relationship_types: Optional[List[str]] = None,
    max_nodes: int = MAX_NODES,
    max_relationships: int = MAX_RELATIONSHIPS,
) -> Dict[str, Any]:
    """Extract investigation-focused subgraph.

    - Validates depth 0..6, max_nodes/relationships bounds.
    - Root must exist (404 else).
    - If case_id provided, intersects neighborhood with case network.
    - Filters by entity_types / relationship_types if provided.
    - Deterministic ordering (sorted ids), truncation flag.
    - Preserves provenance.
    """
    if depth < 0 or depth > MAX_DEPTH:
        raise ValueError(f"depth must be 0..{MAX_DEPTH}")
    if max_nodes < 1 or max_nodes > 500:
        raise ValueError("max_nodes must be 1..500")
    if max_relationships < 1 or max_relationships > 1000:
        raise ValueError("max_relationships must be 1..1000")

    root_entity = graph_repo.get_entity(root_entity_id)
    if not root_entity:
        raise LookupError(f"Entity '{root_entity_id}' not found")

    # Case network if provided
    case_related_ids: Optional[Set[str]] = None
    if case_id:
        case_exists = any(row.get("case_id") == case_id for row in dataset.get("cases", []))
        if not case_exists:
            # Also check via graph (case may be in graph but not dataset)
            if not graph_repo.get_entity(case_id):
                raise LookupError(f"Case '{case_id}' not found")
        # Build case network via graph_repo relationships of case
        case_rels = graph_repo.get_relationships(case_id)
        case_related_ids = {case_id}
        for rel in case_rels:
            if rel.get("relationship_type") in ("RELATED_TO_CASE", "MENTIONED_IN"):
                case_related_ids.add(rel.get("source_id"))
                case_related_ids.add(rel.get("target_id"))
        # If case has no RELATED_TO_CASE edges, fall back to dataset
        if len(case_related_ids) == 1:
            # No graph edges, use dataset's case network? For now keep just root
            pass

    # Depth 0: only root
    if depth == 0:
        entities_list = [root_entity]
        relationships_list: List[Dict[str, Any]] = []
        # Apply filters
        if entity_types and root_entity.get("entity_type") not in entity_types:
            entities_list = []
        stats = {
            "node_count": len(entities_list),
            "edge_count": 0,
            "depth": depth,
            "truncated": False,
        }
        return {
            "case_id": case_id,
            "root_entity": root_entity,
            "depth": depth,
            "entities": sorted(entities_list, key=lambda e: e.get("entity_id", "")),
            "relationships": [],
            "statistics": stats,
            "truncated": False,
            "provenance": [{"source": "graph_repo", "analysis_type": "neighborhood", "timestamp": _now_iso()}],
        }

    # Get neighborhood via graph repo (depth up to 6)
    try:
        nb = graph_repo.neighborhood(root_entity_id, depth=depth)
    except Exception as exc:
        raise LookupError(f"Neighborhood failed for '{root_entity_id}': {exc}") from exc

    # Collect entity ids from neighborhood nodes
    nb_ids = {n.get("entity_id") for n in nb.get("nodes", []) if n.get("entity_id")}
    nb_ids.add(root_entity_id)

    # Intersect with case network if provided
    if case_related_ids is not None:
        nb_ids = nb_ids.intersection(case_related_ids)

    # Apply entity type filter
    entities_list = []
    for eid in sorted(nb_ids):
        ent = graph_repo.get_entity(eid)
        if not ent:
            # Try dataset fallback
            for key, rows in dataset.items():
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if row.get("entity_id") == eid:
                        ent = row
                        break
                if ent:
                    break
        if not ent:
            continue
        if entity_types and ent.get("entity_type") not in entity_types:
            continue
        entities_list.append(ent)

    # Collect relationships among those entities
    # Use graph_repo.get_relationships for each entity, deduplicate, filter by relationship_types, limit
    rel_map: Dict[str, Dict[str, Any]] = {}
    for eid in sorted(nb_ids):
        try:
            rels = graph_repo.get_relationships(eid)
        except Exception:
            rels = []
        for rel in rels:
            rid = rel.get("relationship_id")
            if not rid or rid in rel_map:
                continue
            # Only keep if both endpoints in nb_ids (closed subgraph) and passes filter
            src, tgt = rel.get("source_id"), rel.get("target_id")
            if src not in nb_ids or tgt not in nb_ids:
                continue
            if relationship_types and rel.get("relationship_type") not in relationship_types:
                continue
            rel_map[rid] = rel

    relationships_list = sorted(rel_map.values(), key=lambda r: r.get("relationship_id", ""))

    # Apply truncation limits deterministically
    truncated = False
    if len(entities_list) > max_nodes:
        entities_list = sorted(entities_list, key=lambda e: e.get("entity_id", ""))[:max_nodes]
        truncated = True
        # Also trim relationships to those among truncated entities
        truncated_ids = {e.get("entity_id") for e in entities_list}
        relationships_list = [r for r in relationships_list if r.get("source_id") in truncated_ids and r.get("target_id") in truncated_ids]

    if len(relationships_list) > max_relationships:
        relationships_list = sorted(relationships_list, key=lambda r: r.get("relationship_id", ""))[:max_relationships]
        truncated = True

    # Statistics
    ent_type_counts = Counter(e.get("entity_type", "Unknown") for e in entities_list)
    rel_type_counts = Counter(r.get("relationship_type", "Unknown") for r in relationships_list)
    stats = {
        "node_count": len(entities_list),
        "edge_count": len(relationships_list),
        "entity_type_counts": dict(sorted(ent_type_counts.items())),
        "relationship_type_counts": dict(sorted(rel_type_counts.items())),
        "depth": depth,
        "truncated": truncated,
        "max_nodes": max_nodes,
        "max_relationships": max_relationships,
    }

    provenance = [
        {"source": "graph_repo", "analysis_type": "neighborhood", "timestamp": _now_iso(), "root_entity_id": root_entity_id, "depth": depth},
    ]
    if case_id:
        provenance.append({"source": "dataset", "analysis_type": "case_network", "timestamp": _now_iso(), "case_id": case_id})
    return {
        "case_id": case_id,
        "root_entity": root_entity,
        "depth": depth,
        "entities": sorted(entities_list, key=lambda e: e.get("entity_id", "")),
        "relationships": sorted(relationships_list, key=lambda r: r.get("relationship_id", "")),
        "statistics": stats,
        "truncated": truncated,
        "provenance": provenance,
    }


# ---------------------------------------------------------------------------
# Multi-hop path (investigator-friendly)
# ---------------------------------------------------------------------------

def investigation_path(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    source_id: str,
    target_id: str,
    max_depth: int = 6,
    case_id: Optional[str] = None,
    relationship_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Investigator-friendly path: nodes with entity details, edges with provenance."""
    if max_depth < 1 or max_depth > MAX_DEPTH:
        raise ValueError(f"max_depth must be 1..{MAX_DEPTH}")
    src_ent = graph_repo.get_entity(source_id)
    if not src_ent:
        raise LookupError(f"Source entity '{source_id}' not found")
    tgt_ent = graph_repo.get_entity(target_id)
    if not tgt_ent:
        raise LookupError(f"Target entity '{target_id}' not found")
    if case_id:
        case_exists = any(row.get("case_id") == case_id for row in dataset.get("cases", []))
        if not case_exists and not graph_repo.get_entity(case_id):
            raise LookupError(f"Case '{case_id}' not found")

    # Use graph repo shortest path
    result = graph_repo.shortest_path(source_id, target_id, max_depth=max_depth)
    if not result or not result.get("found"):
        return {
            "found": False,
            "hop_count": None,
            "nodes": [],
            "edges": [],
            "relationship_sequence": [],
            "provenance": [{"source": "graph_repo", "analysis_type": "shortest_path", "timestamp": _now_iso()}],
        }

    # Enrich nodes and edges
    entity_ids: List[str] = result.get("entities", [])
    rel_types: List[str] = result.get("relationships", [])
    nodes: List[Dict[str, Any]] = []
    for eid in entity_ids:
        ent = graph_repo.get_entity(eid)
        if not ent:
            # Fallback to dataset
            for key, rows in dataset.items():
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if row.get("entity_id") == eid:
                        ent = row
                        break
                if ent:
                    break
        nodes.append(ent or {"entity_id": eid, "entity_type": "Unknown"})

    # For edges, we need to find actual relationship objects along the path
    # The shortest_path returns only relationship types, not ids. We need to resolve via get_relationships
    # For each hop, find the relationship between the two entities (pick first matching type)
    edges: List[Dict[str, Any]] = []
    relationship_sequence: List[str] = []
    for i in range(len(entity_ids) - 1):
        src, tgt = entity_ids[i], entity_ids[i + 1]
        # Find relationship between src and tgt (any direction)
        candidates = []
        for rel in graph_repo.get_relationships(src):
            if (rel.get("source_id") == src and rel.get("target_id") == tgt) or (rel.get("source_id") == tgt and rel.get("target_id") == src):
                if relationship_types and rel.get("relationship_type") not in relationship_types:
                    continue
                candidates.append(rel)
        # Deterministic: sort by relationship_id
        candidates = sorted(candidates, key=lambda r: r.get("relationship_id", ""))
        # Prefer the type that matches the shortest_path's type at this hop if available
        chosen = None
        if i < len(rel_types):
            for c in candidates:
                if c.get("relationship_type") == rel_types[i]:
                    chosen = c
                    break
        if not chosen and candidates:
            chosen = candidates[0]
        if chosen:
            edges.append(chosen)
            relationship_sequence.append(chosen.get("relationship_type", rel_types[i] if i < len(rel_types) else "UNKNOWN"))
        else:
            # No relationship found (should not happen), use placeholder
            relationship_sequence.append(rel_types[i] if i < len(rel_types) else "UNKNOWN")
            edges.append({
                "relationship_id": f"placeholder-{src}-{tgt}",
                "source_id": src,
                "target_id": tgt,
                "relationship_type": rel_types[i] if i < len(rel_types) else "UNKNOWN",
                "provenance": "inferred",
            })

    # If case filter, ensure all nodes are in case network (optional)
    if case_id:
        case_related = set()
        for rel in graph_repo.get_relationships(case_id):
            if rel.get("relationship_type") in ("RELATED_TO_CASE", "MENTIONED_IN"):
                case_related.add(rel.get("source_id"))
                case_related.add(rel.get("target_id"))
        case_related.add(case_id)
        # If path leaves case network, still return but note in provenance
        in_case = all(n.get("entity_id") in case_related for n in nodes)
        provenance_extra = {"case_id": case_id, "in_case_network": in_case}
    else:
        provenance_extra = {}

    return {
        "found": True,
        "hop_count": result.get("length"),
        "nodes": nodes,
        "edges": edges,
        "relationship_sequence": relationship_sequence,
        "provenance": [
            {"source": "graph_repo", "analysis_type": "shortest_path", "timestamp": _now_iso(), "max_depth": max_depth, **provenance_extra}
        ],
    }


# ---------------------------------------------------------------------------
# Evidence & Findings
# ---------------------------------------------------------------------------

def _deterministic_finding_id(case_id: Optional[str], finding_type: str, entity_ids: List[str], salt: str = "") -> str:
    base = "|".join(sorted(entity_ids)) + "|" + finding_type + "|" + (case_id or "global") + "|" + salt
    return f"finding-{_hash_id(base)}"


def collect_evidence(
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    paths: List[Dict[str, Any]],
    indicators: List[Dict[str, Any]],
    temporal: List[Dict[str, Any]],
    chains: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Aggregate evidence items with provenance."""
    evidence: List[Dict[str, Any]] = []
    for ent in sorted(entities, key=lambda e: e.get("entity_id", ""))[:20]:
        evidence.append({
            "evidence_id": f"ev-entity-{ent.get('entity_id')}",
            "evidence_type": "entity",
            "description": f"Entity {ent.get('entity_id')} ({ent.get('entity_type')}) present in investigation subgraph",
            "entity_ids": [ent.get("entity_id")],
            "relationship_ids": [],
            "indicator_ids": [],
            "provenance": [{"source": "graph_repo", "analysis_type": "subgraph", "timestamp": _now_iso()}],
            "created_at": _now_iso(),
        })
    for rel in sorted(relationships, key=lambda r: r.get("relationship_id", ""))[:20]:
        evidence.append({
            "evidence_id": f"ev-rel-{rel.get('relationship_id')}",
            "evidence_type": "relationship",
            "description": f"Relationship {rel.get('relationship_id')} {rel.get('relationship_type')} {rel.get('source_id')}→{rel.get('target_id')}",
            "entity_ids": [rel.get("source_id"), rel.get("target_id")],
            "relationship_ids": [rel.get("relationship_id")],
            "indicator_ids": [],
            "provenance": [{"source": "graph_repo", "analysis_type": "relationship", "timestamp": _now_iso(), "extraction_method": rel.get("extraction_method")}],
            "created_at": _now_iso(),
        })
    for path in paths[:5]:
        if path.get("found"):
            evidence.append({
                "evidence_id": f"ev-path-{_hash_id(str(path.get('nodes')))}",
                "evidence_type": "path",
                "description": f"Path {path.get('hop_count')} hops between {path.get('nodes', [{}])[0].get('entity_id') if path.get('nodes') else '?'} and {path.get('nodes', [{}])[-1].get('entity_id') if path.get('nodes') else '?'}",
                "entity_ids": [n.get("entity_id") for n in path.get("nodes", [])],
                "relationship_ids": [e.get("relationship_id") for e in path.get("edges", []) if e.get("relationship_id")],
                "indicator_ids": [],
                "provenance": path.get("provenance", []),
                "created_at": _now_iso(),
            })
    for ind in indicators[:5]:
        evidence.append({
            "evidence_id": f"ev-ind-{ind.get('indicator_id', _hash_id(str(ind)))}",
            "evidence_type": "indicator",
            "description": ind.get("explanation", "")[:200],
            "entity_ids": ind.get("entity_ids", []),
            "relationship_ids": ind.get("relationship_ids", []),
            "indicator_ids": [ind.get("indicator_id")],
            "provenance": [{"source": "network_analysis", "analysis_type": ind.get("indicator_type"), "timestamp": _now_iso()}],
            "created_at": _now_iso(),
        })
    return evidence


def generate_findings(
    case_id: Optional[str],
    root_entity_id: Optional[str],
    subgraph: Dict[str, Any],
    paths: List[Dict[str, Any]],
    entities_snapshot: Dict[str, Any],
    relationships: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Deterministic candidate findings from existing intelligence.

    Never produces guilt/criminality scores; uses neutral terminology.
    """
    findings: List[Dict[str, Any]] = []
    entities_list: List[Dict[str, Any]] = subgraph.get("entities", [])
    rels_list: List[Dict[str, Any]] = subgraph.get("relationships", [])

    # Build snapshot for analysis helpers
    snapshot: Dict[str, Any] = {}
    for ent in entities_list:
        eid = ent.get("entity_id")
        etype = ent.get("entity_type", "Unknown")
        if eid:
            snapshot[eid] = (etype, ent)
    # If snapshot empty, fallback to full snapshot
    if not snapshot and entities_snapshot:
        snapshot = entities_snapshot
        rels_list = relationships

    # Run intelligence
    centrality = compute_centrality(snapshot, rels_list) if snapshot else {"betweenness": {}}
    bridges = find_bridges(snapshot, rels_list, top_k=5) if snapshot else []
    temporal = analyze_temporal(rels_list)
    chains = find_transaction_chains(rels_list)
    strengths = compute_relationship_strength(rels_list)
    indicators = generate_indicators(snapshot, rels_list) if snapshot else []

    # Finding 1: bridge entity connecting communities
    for b in bridges[:2]:
        eid = b["entity_id"]
        finding_id = _deterministic_finding_id(case_id, "bridge_entity", [eid], b["metric"])
        findings.append({
            "finding_id": finding_id,
            "finding_type": "bridge_entity",
            "title": f"Bridge entity connecting network regions: {eid}",
            "severity": "MEDIUM" if b["metric"] == "articulation_point" else "LOW",
            "explanation": (
                f"Observed network pattern: entity {eid} ({b['entity_type']}) {b['explanation']} "
                f"This was selected because high betweenness/community-boundary indicates it links otherwise separated groups. "
                f"Supporting evidence includes {len(b['evidence'])} relationships. This is a candidate finding for investigator review, not a guilt assessment."
            ),
            "entity_ids": [eid],
            "relationship_ids": b["evidence"],
            "supporting_paths": [],
            "indicators": [ind for ind in indicators if eid in ind.get("entity_ids", [])][:2],
            "temporal_evidence": [],
            "transaction_evidence": [],
            "centrality_context": {"betweenness": centrality.get("betweenness", {}).get(eid), "degree": centrality.get("degree", {}).get(eid)},
            "community_context": None,
            "evidence": [],
            "provenance": [{"source": "network_analysis", "analysis_type": b["metric"], "timestamp": _now_iso()}],
            "created_at": _now_iso(),
        })

    # Finding 2: temporal burst
    for t in temporal[:2]:
        eids = t.get("entity_ids", [])
        if not eids:
            eids = ["unknown"]
        finding_id = _deterministic_finding_id(case_id, "temporal_burst", eids, t["time_window"])
        findings.append({
            "finding_id": finding_id,
            "finding_type": "temporal_burst",
            "title": f"Repeated interaction burst: {t['indicator_type']}",
            "severity": "MEDIUM",
            "explanation": (
                f"Observed pattern: {t['explanation']} This was selected because the count exceeds baseline threshold, "
                f"indicating unusually dense activity in that window. Supporting temporal evidence and relationships are listed."
            ),
            "entity_ids": eids,
            "relationship_ids": t.get("evidence", []),
            "supporting_paths": [],
            "indicators": [],
            "temporal_evidence": [t],
            "transaction_evidence": [],
            "centrality_context": None,
            "community_context": None,
            "evidence": [],
            "provenance": [{"source": "network_analysis", "analysis_type": "temporal", "timestamp": _now_iso()}],
            "created_at": _now_iso(),
        })

    # Finding 3: transaction chain
    for ch in chains[:2]:
        eids = [ch["source_account"]] + ch["intermediate_accounts"] + [ch["destination_account"]]
        finding_id = _deterministic_finding_id(case_id, "transaction_chain", eids, ch["chain_id"])
        findings.append({
            "finding_id": finding_id,
            "finding_type": "transaction_chain",
            "title": f"Transaction chain {ch['hop_count']} hops: {ch['source_account']} → {ch['destination_account']}",
            "severity": "MEDIUM" if ch["hop_count"] >= 3 else "LOW",
            "explanation": (
                f"Observed pattern: {ch['explanation']} This was selected because directed chains of TRANSFERRED_TO relationships "
                f"show multi-hop fund movement. This is an observed pattern, not an accusation; review provenance and transaction metadata."
            ),
            "entity_ids": eids,
            "relationship_ids": ch["evidence"],
            "supporting_paths": [],
            "indicators": [],
            "temporal_evidence": [],
            "transaction_evidence": [ch],
            "centrality_context": None,
            "community_context": None,
            "evidence": [],
            "provenance": [{"source": "network_analysis", "analysis_type": "transaction_chain", "timestamp": _now_iso()}],
            "created_at": _now_iso(),
        })

    # Finding 4: strong relationship
    for s in strengths[:1]:
        if s["interaction_strength"] < 0.6:
            continue
        eids = [s["source_id"], s["target_id"]]
        finding_id = _deterministic_finding_id(case_id, "strong_relationship", eids, s["relationship_id"])
        findings.append({
            "finding_id": finding_id,
            "finding_type": "strong_relationship",
            "title": f"Strong interaction: {s['relationship_type']} {s['source_id']} ↔ {s['target_id']}",
            "severity": "LOW",
            "explanation": (
                f"Observed pattern: {s['explanation']} This was selected because interaction_strength {s['interaction_strength']} is above typical, "
                f"supported by pair frequency and provenance. This indicates observed relationship intensity, not criminal association."
            ),
            "entity_ids": eids,
            "relationship_ids": [s["relationship_id"]],
            "supporting_paths": [],
            "indicators": [],
            "temporal_evidence": [],
            "transaction_evidence": [],
            "centrality_context": None,
            "community_context": None,
            "evidence": [],
            "provenance": [{"source": "network_analysis", "analysis_type": "relationship_strength", "timestamp": _now_iso()}],
            "created_at": _now_iso(),
        })
        break  # only one

    # Deduplicate and limit
    seen = set()
    deduped = []
    for f in sorted(findings, key=lambda x: x["finding_id"]):
        if f["finding_id"] not in seen:
            seen.add(f["finding_id"])
            deduped.append(f)
    return deduped[:MAX_FINDINGS]


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def investigation_snapshot(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    case_id: Optional[str],
    root_entity_id: str,
    depth: int = 2,
    entity_types: Optional[List[str]] = None,
    relationship_types: Optional[List[str]] = None,
    include_findings: bool = True,
    include_paths: bool = True,
    max_nodes: int = MAX_NODES,
) -> Dict[str, Any]:
    """Deterministic snapshot for investigation workspace."""
    subgraph = investigation_subgraph(
        graph_repo, dataset, root_entity_id, depth=depth, case_id=case_id,
        entity_types=entity_types, relationship_types=relationship_types, max_nodes=max_nodes,
    )
    # Build snapshot entities for analysis
    snapshot_entities: Dict[str, Any] = {}
    for ent in subgraph["entities"]:
        eid = ent.get("entity_id")
        etype = ent.get("entity_type")
        if eid and etype:
            snapshot_entities[eid] = (etype, ent)

    # Paths: from root to a few other entities in subgraph (up to 5)
    paths: List[Dict[str, Any]] = []
    if include_paths and len(subgraph["entities"]) > 1:
        # Pick up to 3 targets sorted, excluding root, that are reachable
        targets = sorted([e.get("entity_id") for e in subgraph["entities"] if e.get("entity_id") != root_entity_id])[:3]
        for tgt in targets:
            try:
                p = investigation_path(graph_repo, dataset, root_entity_id, tgt, max_depth=min(depth + 2, MAX_DEPTH), case_id=case_id)
                if p.get("found"):
                    paths.append(p)
            except Exception:
                continue
            if len(paths) >= 5:
                break

    # Findings
    findings: List[Dict[str, Any]] = []
    if include_findings:
        findings = generate_findings(case_id, root_entity_id, subgraph, paths, snapshot_entities, subgraph["relationships"])

    # Evidence aggregation
    all_indicators = []
    if snapshot_entities:
        all_indicators = generate_indicators(snapshot_entities, subgraph["relationships"])
    evidence = collect_evidence(subgraph["entities"], subgraph["relationships"], paths, all_indicators, [], [])

    snapshot_id = f"snapshot-{_hash_id(case_id or 'global', root_entity_id, str(depth), str(max_nodes))}"
    return {
        "snapshot_id": snapshot_id,
        "case_id": case_id,
        "root_entity": subgraph["root_entity"],
        "depth": depth,
        "entities": subgraph["entities"],
        "relationships": subgraph["relationships"],
        "paths": paths,
        "findings": findings,
        "evidence": evidence,
        "statistics": subgraph["statistics"],
        "generated_at": _now_iso(),
        "provenance": subgraph["provenance"] + [{"source": "investigation_engine", "analysis_type": "snapshot", "timestamp": _now_iso()}],
    }
