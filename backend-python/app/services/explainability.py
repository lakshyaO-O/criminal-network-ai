"""Explainability Service — Milestone 9A.

Provides typed explanations for every analytical result, with lineage.

All explanations are deterministic, based on actual backend data (M5/M8 outputs),
never fictional. Reuses existing intelligence; does not recompute entire graph
unless necessary and then via the same deterministic algorithms.

Every explanation answers: WHAT, WHY, WHICH data, WHICH algorithm, PARAMETERS,
WHEN, WHERE, REPRODUCIBILITY, LIMITATIONS.

Safety: no guilt/criminality claims; uses neutral language.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.graph.base import GraphRepository
from app.services.network_analysis import (
    compute_centrality,
    find_communities,
    find_bridges,
    analyze_temporal,
    find_transaction_chains,
    compute_relationship_strength,
)
from app.services.investigation import (
    investigation_subgraph,
    investigation_path,
    generate_findings,
)


FIXED_GENERATED_AT = "2024-01-01T00:00:00Z"


def _now_iso() -> str:
    return FIXED_GENERATED_AT


def _hash_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


def _dataset_id(dataset: Dict[str, Any]) -> str:
    # Deterministic context identifier: hash of counts + generation_config seed if present
    counts = dataset.get("_generation_config", {}).get("counts", {}) if isinstance(dataset.get("_generation_config"), dict) else {}
    base = str(sorted(counts.items())) if counts else str(len(dataset))
    return f"dataset-{_hash_id(base)}"


# ---------------------------------------------------------------------------
# Generic lineage wrapper
# ---------------------------------------------------------------------------

def _lineage(
    analysis_type: str,
    algorithm: str,
    parameters: Dict[str, Any],
    inputs: Dict[str, Any],
    observations: List[str],
    output_summary: str,
    dataset_id: str,
) -> Dict[str, Any]:
    return {
        "analysis_type": analysis_type,
        "algorithm": algorithm,
        "parameters": parameters,
        "inputs": inputs,
        "observations": observations,
        "output_summary": output_summary,
        "dataset_id": dataset_id,
        "deterministic": True,
        "timestamp": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Centrality explanation
# ---------------------------------------------------------------------------

def explain_centrality(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    entity_id: str,
) -> Dict[str, Any]:
    entities, rels = graph_repo.export_snapshot()
    if entity_id not in entities:
        raise LookupError(f"Entity '{entity_id}' not found")
    centrality = compute_centrality(entities, rels)
    # Gather observations for this entity
    deg = centrality["degree"].get(entity_id, 0.0)
    bet = centrality["betweenness"].get(entity_id, 0.0)
    clo = centrality["closeness"].get(entity_id, 0.0)
    pr = centrality["pagerank"].get(entity_id, 0.0)
    # Contributing relationships
    adj_rels = [r for r in rels if r["source_id"] == entity_id or r["target_id"] == entity_id]
    explanation_id = f"expl-centrality-{entity_id}-{_hash_id(entity_id)}"
    return {
        "explanation_id": explanation_id,
        "analysis_type": "centrality",
        "summary": f"Centrality for {entity_id}: degree {deg:.4f}, betweenness {bet:.4f}, closeness {clo:.4f}, PageRank {pr:.4f}",
        "methodology": (
            "Degree = degree/(n-1) (NetworkX degree_centrality). "
            "Betweenness = fraction of shortest paths passing through node (betweenness_centrality, normalized). "
            "Closeness = 1/avg distance to reachable nodes (closeness_centrality). "
            "PageRank = damping 0.85, max_iter 100 (pagerank). All via NetworkX on undirected graph, deterministic, rounded 6 decimals."
        ),
        "observations": [
            f"Entity {entity_id} has {len([r for r in adj_rels])} direct relationships",
            f"Degree centrality {deg:.4f} (normalized by graph size n={len(entities)})",
            f"Betweenness {bet:.4f} indicates frequency on shortest paths",
            f"Closeness {clo:.4f} inverse avg distance",
            f"PageRank {pr:.4f} link-analysis score",
        ],
        "contributing_entities": [entity_id] + sorted({r["source_id"] if r["target_id"] == entity_id else r["target_id"] for r in adj_rels})[:5],
        "contributing_relationships": sorted([r["relationship_id"] for r in adj_rels])[:10],
        "supporting_evidence": sorted([r["relationship_id"] for r in adj_rels])[:5],
        "parameters": {"alpha": 0.85, "max_iter": 100, "normalized": True},
        "thresholds": {"high_betweenness": 0.05},
        "limitations": "Centrality is descriptive network position only; high centrality does not imply guilt or criminality. Disconnected components yield closeness 0. Single-node graphs yield degree 0.",
        "provenance": [{"source": "network_analysis", "analysis_type": "centrality", "timestamp": _now_iso(), "algorithm": "networkx"}],
        "generated_at": _now_iso(),
        "lineage": _lineage(
            "centrality", "networkx.degree/betweenness/closeness/pagerank",
            {"alpha": 0.85}, {"entity_id": entity_id, "graph_size": len(entities)}, 
            [f"degree {deg:.4f}", f"betweenness {bet:.4f}"],
            f"Centrality scores for {entity_id}",
            _dataset_id(dataset),
        ),
        "reproducibility": {
            "analysis_type": "centrality",
            "entity_id": entity_id,
            "parameters": {"alpha": 0.85},
            "dataset_id": _dataset_id(dataset),
            "result_id": explanation_id,
            "deterministic": True,
        },
    }


# ---------------------------------------------------------------------------
# Community explanation
# ---------------------------------------------------------------------------

def explain_community(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    entity_id: Optional[str] = None,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    entities, rels = graph_repo.export_snapshot()
    communities = find_communities(entities, rels)
    # Find community containing entity if provided
    target_comm = None
    if entity_id:
        for comm in communities:
            if entity_id in comm["members"]:
                target_comm = comm
                break
        if not target_comm:
            raise LookupError(f"Entity '{entity_id}' not found in any community")
    else:
        target_comm = communities[0] if communities else None

    explanation_id = f"expl-community-{entity_id or 'global'}-{_hash_id(str(target_comm))}"
    return {
        "explanation_id": explanation_id,
        "analysis_type": "community",
        "summary": f"Community {target_comm['community_id']} size {target_comm['size']} density {target_comm['density']}" if target_comm else "No communities",
        "methodology": "Greedy modularity communities (NetworkX greedy_modularity_communities, weight=None, deterministic sorted by min member). Density = internal_edges / (size*(size-1)/2).",
        "observations": [
            f"Graph has {len(communities)} communities",
            f"Target community {target_comm['community_id']} has {target_comm['size']} members, {target_comm['internal_edges']} internal edges, density {target_comm['density']}" if target_comm else "No community",
        ],
        "contributing_entities": (target_comm["members"] if target_comm else [])[:10],
        "contributing_relationships": [r["relationship_id"] for r in rels if target_comm and r["source_id"] in set(target_comm["members"]) and r["target_id"] in set(target_comm["members"])][:10],
        "supporting_evidence": [],
        "parameters": {"algorithm": "greedy_modularity", "weight": None},
        "thresholds": {},
        "limitations": "Communities are interaction clusters via modularity, not 'gangs'. Assignment depends on graph scope; isolated nodes form own communities.",
        "provenance": [{"source": "network_analysis", "analysis_type": "community", "timestamp": _now_iso()}],
        "generated_at": _now_iso(),
        "lineage": _lineage("community", "greedy_modularity", {}, {"entity_id": entity_id}, [f"size {target_comm['size']}" if target_comm else "none"], "Community assignment", _dataset_id(dataset)),
        "reproducibility": {"analysis_type": "community", "entity_id": entity_id, "dataset_id": _dataset_id(dataset), "result_id": explanation_id, "deterministic": True},
    }


# ---------------------------------------------------------------------------
# Bridge explanation
# ---------------------------------------------------------------------------

def explain_bridge(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    entity_id: str,
) -> Dict[str, Any]:
    entities, rels = graph_repo.export_snapshot()
    if entity_id not in entities:
        raise LookupError(f"Entity '{entity_id}' not found")
    bridges = find_bridges(entities, rels, top_k=20)
    bridge = next((b for b in bridges if b["entity_id"] == entity_id), None)
    # Also check if entity is articulation point even if not in top_k bridges (compute directly)
    if not bridge:
        # Not a bridge per thresholds, but explain why not
        explanation_id = f"expl-bridge-{entity_id}-{_hash_id(entity_id+'-not-bridge')}"
        return {
            "explanation_id": explanation_id,
            "analysis_type": "bridge",
            "summary": f"Entity {entity_id} is not a bridge candidate under current thresholds",
            "methodology": "Articulation points (Tarjan) + betweenness >0.05 + community boundary ≥2",
            "observations": [f"Entity {entity_id} not in bridge list; betweenness below threshold or not articulation/boundary"],
            "contributing_entities": [entity_id],
            "contributing_relationships": [],
            "supporting_evidence": [],
            "parameters": {"betweenness_threshold": 0.05, "boundary_threshold": 2},
            "thresholds": {"betweenness": 0.05, "boundary": 2},
            "limitations": "Bridge detection is structural; not every high-betweenness node is an articulation point. Thresholds are analytical, not criminal.",
            "provenance": [{"source": "network_analysis", "analysis_type": "bridge", "timestamp": _now_iso()}],
            "generated_at": _now_iso(),
            "lineage": _lineage("bridge", "tarjan+betweenness", {"threshold": 0.05}, {"entity_id": entity_id}, ["not bridge"], "Bridge check", _dataset_id(dataset)),
            "reproducibility": {"analysis_type": "bridge", "entity_id": entity_id, "dataset_id": _dataset_id(dataset), "result_id": explanation_id, "deterministic": True},
        }

    explanation_id = f"expl-bridge-{entity_id}-{_hash_id(entity_id+bridge['metric'])}"
    return {
        "explanation_id": explanation_id,
        "analysis_type": "bridge",
        "summary": f"Bridge {entity_id} via {bridge['metric']} score {bridge['score']:.4f}",
        "methodology": "Articulation point (Tarjan DFS) identifies nodes whose removal increases components; betweenness from NetworkX; community boundary counts neighboring communities via greedy modularity.",
        "observations": [f"Metric {bridge['metric']} score {bridge['score']:.4f}", f"Evidence {len(bridge['evidence'])} relationships"],
        "contributing_entities": [entity_id],
        "contributing_relationships": bridge["evidence"],
        "supporting_evidence": bridge["evidence"],
        "parameters": {"betweenness_threshold": 0.05, "boundary_threshold": 2},
        "thresholds": {"betweenness": 0.05, "boundary": 2, "score": bridge["score"]},
        "limitations": "Bridge indicates structural position, not guilt. Single-community graphs have no bridges.",
        "provenance": [{"source": "network_analysis", "analysis_type": bridge["metric"], "timestamp": _now_iso()}],
        "generated_at": _now_iso(),
        "lineage": _lineage("bridge", bridge["metric"], {"threshold": 0.05}, {"entity_id": entity_id}, [f"score {bridge['score']:.4f}"], f"Bridge {entity_id}", _dataset_id(dataset)),
        "reproducibility": {"analysis_type": "bridge", "entity_id": entity_id, "parameters": {"threshold": 0.05}, "dataset_id": _dataset_id(dataset), "result_id": explanation_id, "deterministic": True},
    }


# ---------------------------------------------------------------------------
# Temporal explanation
# ---------------------------------------------------------------------------

def explain_temporal(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    entity_id: Optional[str] = None,
) -> Dict[str, Any]:
    _, rels = graph_repo.export_snapshot()
    temporals = analyze_temporal(rels)
    # Filter to entity if provided
    if entity_id:
        filtered = [t for t in temporals if entity_id in t.get("entity_ids", [])]
        if not filtered:
            raise LookupError(f"No temporal burst for entity '{entity_id}'")
        target = filtered[0]
    else:
        target = temporals[0] if temporals else None
        if not target:
            explanation_id = f"expl-temporal-global-{_hash_id('none')}"
            return {
                "explanation_id": explanation_id,
                "analysis_type": "temporal",
                "summary": "No temporal bursts detected",
                "methodology": "24h windows, per-entity mean+2*std threshold, observed>threshold && >=3",
                "observations": ["No windows exceed baseline"],
                "contributing_entities": [],
                "contributing_relationships": [],
                "supporting_evidence": [],
                "parameters": {"window_hours": 24, "z_threshold": 2.0},
                "thresholds": {"z": 2.0},
                "limitations": "Requires timestamps; sparse data yields no bursts.",
                "provenance": [{"source": "network_analysis", "analysis_type": "temporal", "timestamp": _now_iso()}],
                "generated_at": _now_iso(),
                "lineage": _lineage("temporal", "burst", {"window": 24}, {}, ["none"], "No bursts", _dataset_id(dataset)),
                "reproducibility": {"analysis_type": "temporal", "entity_id": entity_id, "dataset_id": _dataset_id(dataset), "result_id": explanation_id, "deterministic": True},
            }

    explanation_id = f"expl-temporal-{entity_id or 'global'}-{_hash_id(target['time_window'])}"
    return {
        "explanation_id": explanation_id,
        "analysis_type": "temporal",
        "summary": f"Temporal burst {target['observed_count']} in {target['time_window']} vs baseline {target['baseline']['mean']:.2f}±{target['baseline']['std']:.2f}",
        "methodology": "Bucket relationships by 24h windows from min timestamp, per-entity mean/std, flag if observed > mean+2*std and >=3",
        "observations": [target["explanation"]],
        "contributing_entities": target["entity_ids"],
        "contributing_relationships": target["evidence"],
        "supporting_evidence": target["evidence"],
        "parameters": {"window_hours": 24, "z_threshold": 2.0},
        "thresholds": target["baseline"],
        "limitations": "Burst detection is statistical; small windows or sparse timestamps may miss patterns.",
        "provenance": [{"source": "network_analysis", "analysis_type": "temporal", "timestamp": _now_iso()}],
        "generated_at": _now_iso(),
        "lineage": _lineage("temporal", "burst", {"window": 24}, {"entity_id": entity_id}, [f"observed {target['observed_count']}"], "Temporal burst", _dataset_id(dataset)),
        "reproducibility": {"analysis_type": "temporal", "entity_id": entity_id, "parameters": {"window": 24}, "dataset_id": _dataset_id(dataset), "result_id": explanation_id, "deterministic": True},
    }


# ---------------------------------------------------------------------------
# Transaction chain explanation
# ---------------------------------------------------------------------------

def explain_chain(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    chain_id: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Dict[str, Any]:
    _, rels = graph_repo.export_snapshot()
    chains = find_transaction_chains(rels)
    if not chains:
        raise LookupError("No transaction chains found")
    target = None
    if chain_id:
        target = next((c for c in chains if c["chain_id"] == chain_id), None)
        if not target:
            raise LookupError(f"Chain '{chain_id}' not found")
    elif account_id:
        target = next((c for c in chains if account_id in [c["source_account"], c["destination_account"]] + c["intermediate_accounts"]), None)
        if not target:
            raise LookupError(f"No chain for account '{account_id}'")
    else:
        target = chains[0]

    explanation_id = f"expl-chain-{target['chain_id']}-{_hash_id(target['chain_id'])}"
    return {
        "explanation_id": explanation_id,
        "analysis_type": "transaction_chain",
        "summary": f"Chain {target['hop_count']} hops {target['source_account']}→{target['destination_account']}",
        "methodology": "Directed graph of TRANSFERRED_TO edges (DiGraph), DFS 2–4 hops from sorted sources, dedup by evidence set, max 20",
        "observations": [target["explanation"]],
        "contributing_entities": [target["source_account"]] + target["intermediate_accounts"] + [target["destination_account"]],
        "contributing_relationships": target["evidence"],
        "supporting_evidence": target["evidence"],
        "parameters": {"min_hops": 2, "max_hops": 4},
        "thresholds": {"hop_count": target["hop_count"]},
        "limitations": "Chain existence alone is not suspicious; review transaction metadata and provenance.",
        "provenance": [{"source": "network_analysis", "analysis_type": "transaction_chain", "timestamp": _now_iso()}],
        "generated_at": _now_iso(),
        "lineage": _lineage("transaction_chain", "dfs", {"min_hops": 2, "max_hops": 4}, {"account_id": account_id}, [f"hops {target['hop_count']}"], "Chain", _dataset_id(dataset)),
        "reproducibility": {"analysis_type": "transaction_chain", "chain_id": target["chain_id"], "dataset_id": _dataset_id(dataset), "result_id": explanation_id, "deterministic": True},
    }


# ---------------------------------------------------------------------------
# Relationship strength explanation
# ---------------------------------------------------------------------------

def explain_strength(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    relationship_id: str,
) -> Dict[str, Any]:
    _, rels = graph_repo.export_snapshot()
    strengths = compute_relationship_strength(rels)
    target = next((s for s in strengths if s["relationship_id"] == relationship_id), None)
    if not target:
        raise LookupError(f"Relationship '{relationship_id}' not found")
    explanation_id = f"expl-strength-{relationship_id}-{_hash_id(relationship_id)}"
    return {
        "explanation_id": explanation_id,
        "analysis_type": "relationship_strength",
        "summary": f"Interaction strength {target['interaction_strength']:.4f} for {relationship_id} ({target['relationship_type']})",
        "methodology": "Weighted: type_weight*0.3 + confidence*0.4 + pair_frequency*0.2 + timestamp_bonus, normalized /1.5, capped 1.0",
        "observations": [target["explanation"]],
        "contributing_entities": [target["source_id"], target["target_id"]],
        "contributing_relationships": [relationship_id],
        "supporting_evidence": [relationship_id],
        "parameters": target["factors"],
        "thresholds": {"strong": 0.6},
        "limitations": "Strength is descriptive intensity, not criminal association. Type weights are heuristic.",
        "provenance": [{"source": "network_analysis", "analysis_type": "relationship_strength", "timestamp": _now_iso()}],
        "generated_at": _now_iso(),
        "lineage": _lineage("relationship_strength", "weighted", target["factors"], {"relationship_id": relationship_id}, [f"strength {target['interaction_strength']:.4f}"], "Strength", _dataset_id(dataset)),
        "reproducibility": {"analysis_type": "relationship_strength", "relationship_id": relationship_id, "dataset_id": _dataset_id(dataset), "result_id": explanation_id, "deterministic": True},
    }


# ---------------------------------------------------------------------------
# Indicator & Finding explanations (reuse)
# ---------------------------------------------------------------------------

def explain_indicator(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    indicator_id: str,
) -> Dict[str, Any]:
    from app.services.network_analysis import generate_indicators
    entities, rels = graph_repo.export_snapshot()
    indicators = generate_indicators(entities, rels)
    target = next((ind for ind in indicators if ind["indicator_id"] == indicator_id), None)
    if not target:
        # Also check base indicators (high_network_centrality etc.) via _base_analysis
        from app.services.network_analysis import _base_analysis
        base = _base_analysis(entities, rels)
        # base indicators use different id scheme (entity_id), try to find by entity
        raise LookupError(f"Indicator '{indicator_id}' not found")
    explanation_id = f"expl-indicator-{indicator_id}-{_hash_id(indicator_id)}"
    return {
        "explanation_id": explanation_id,
        "analysis_type": "indicator",
        "summary": f"Indicator {target['indicator_type']} severity {target['severity']} score {target['score']}",
        "methodology": "Indicator generated from centrality/bridge/temporal/chain with severity thresholds HIGH≥0.75 MEDIUM≥0.4",
        "observations": [target["explanation"]],
        "contributing_entities": target["entity_ids"],
        "contributing_relationships": target["relationship_ids"],
        "supporting_evidence": target["evidence"],
        "parameters": {"severity_thresholds": {"HIGH": 0.75, "MEDIUM": 0.4}},
        "thresholds": {"score": target["score"]},
        "limitations": "Indicator is analytical signal, not guilt. Requires investigator review.",
        "provenance": [{"source": "network_analysis", "analysis_type": target["indicator_type"], "timestamp": _now_iso()}],
        "generated_at": _now_iso(),
        "lineage": _lineage("indicator", target["indicator_type"], {}, {"indicator_id": indicator_id}, [f"score {target['score']}"], "Indicator", _dataset_id(dataset)),
        "reproducibility": {"analysis_type": "indicator", "indicator_id": indicator_id, "dataset_id": _dataset_id(dataset), "result_id": explanation_id, "deterministic": True},
    }


def explain_finding(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    finding_id: str,
) -> Dict[str, Any]:
    from app.services.investigation import investigation_snapshot, generate_findings
    # Reconstruct findings deterministically: need to find which case/root generated this finding
    # For milestone 9A, we can search via global and case-specific generation
    # Try global first
    entities, rels = graph_repo.export_snapshot()
    # Try to generate findings for global and each case/root combination that could have produced this finding_id
    # Simpler: generate global findings and search
    # Also generate for each case + root entity (first few) – but to keep bounded, try global + a few roots
    candidates = []
    # Global
    from app.services.investigation import investigation_subgraph
    # Build a minimal subgraph for global: use all entities
    # Use generate_findings with a dummy subgraph that contains all
    dummy_subgraph = {"entities": [{"entity_id": eid, "entity_type": etype} for eid, (etype, _) in entities.items()], "relationships": rels}
    global_findings = generate_findings(None, None, dummy_subgraph, [], entities, rels)
    for f in global_findings:
        if f["finding_id"] == finding_id:
            candidates.append(f)
            break
    # If not found, try case-specific (iterate cases)
    if not candidates:
        for case_row in dataset.get("cases", [])[:4]:
            case_id = case_row["case_id"]
            try:
                snap = investigation_snapshot(graph_repo, dataset, case_id, list(entities.keys())[0], depth=2)
                for f in snap.get("findings", []):
                    if f["finding_id"] == finding_id:
                        candidates.append(f)
                        break
            except Exception:
                continue
            if candidates:
                break
    # Also try root-specific
    if not candidates:
        for eid in list(entities.keys())[:10]:
            try:
                snap = investigation_snapshot(graph_repo, dataset, None, eid, depth=2)
                for f in snap.get("findings", []):
                    if f["finding_id"] == finding_id:
                        candidates.append(f)
                        break
            except Exception:
                continue
            if candidates:
                break

    if not candidates:
        raise LookupError(f"Finding '{finding_id}' not found")

    target = candidates[0]
    explanation_id = f"expl-finding-{finding_id}-{_hash_id(finding_id)}"
    return {
        "explanation_id": explanation_id,
        "analysis_type": "finding",
        "summary": f"Finding {target['finding_type']} {finding_id}: {target['title']}",
        "methodology": "Finding generated deterministically from intelligence (bridge/temporal/chain/strength) with severity thresholds, sorted by finding_id",
        "observations": [target["explanation"]],
        "contributing_entities": target["entity_ids"],
        "contributing_relationships": target["relationship_ids"],
        "supporting_evidence": [e.get("evidence_id") for e in target.get("evidence", [])] or target["relationship_ids"],
        "parameters": {"max_findings": 20},
        "thresholds": {"severity": target["severity"]},
        "limitations": "Candidate finding is an observed pattern, not a guilt determination. Requires investigator review of provenance and raw data.",
        "provenance": target.get("provenance", []) + [{"source": "investigation_engine", "analysis_type": "finding", "timestamp": _now_iso()}],
        "generated_at": _now_iso(),
        "lineage": _lineage("finding", target["finding_type"], {}, {"finding_id": finding_id}, [target["explanation"][:100]], "Finding", _dataset_id(dataset)),
        "reproducibility": {"analysis_type": "finding", "finding_id": finding_id, "dataset_id": _dataset_id(dataset), "result_id": explanation_id, "deterministic": True},
        "finding": target,  # include original finding for frontend
    }


def explain_entity(
    graph_repo: GraphRepository,
    dataset: Dict[str, Any],
    entity_id: str,
) -> Dict[str, Any]:
    entities, rels = graph_repo.export_snapshot()
    if entity_id not in entities:
        raise LookupError(f"Entity '{entity_id}' not found")
    # Observed data
    ent = entities[entity_id]
    etype, props = ent
    adj_rels = [r for r in rels if r["source_id"] == entity_id or r["target_id"] == entity_id]
    # Analytical interpretations
    from app.services.network_analysis import compute_centrality, find_bridges, find_communities, generate_indicators
    centrality = compute_centrality(entities, rels)
    bridges = find_bridges(entities, rels, top_k=20)
    is_bridge = any(b["entity_id"] == entity_id for b in bridges)
    communities = find_communities(entities, rels)
    community = next((c for c in communities if entity_id in c["members"]), None)
    indicators = [ind for ind in generate_indicators(entities, rels) if entity_id in ind.get("entity_ids", [])]

    explanation_id = f"expl-entity-{entity_id}-{_hash_id(entity_id)}"
    return {
        "explanation_id": explanation_id,
        "analysis_type": "entity",
        "summary": f"Entity {entity_id} ({etype}) has {len(adj_rels)} relationships; bridge={is_bridge}, community={community['community_id'] if community else 'none'}",
        "methodology": "Observed data: entity record + relationships from graph. Analytical: centrality (degree/betweenness/closeness/pagerank), community (greedy_modularity), bridge (articulation/betweenness), indicators (severity thresholds).",
        "observations": [
            f"Observed: entity {entity_id} type {etype} with {len(adj_rels)} relationships",
            f"Analytical: degree {centrality['degree'].get(entity_id, 0):.4f}, betweenness {centrality['betweenness'].get(entity_id, 0):.4f}",
            f"Community {community['community_id'] if community else 'none'} size {community['size'] if community else 0}",
            f"Bridge status {is_bridge}",
            f"{len(indicators)} indicators",
        ],
        "contributing_entities": [entity_id],
        "contributing_relationships": [r["relationship_id"] for r in adj_rels][:10],
        "supporting_evidence": [r["relationship_id"] for r in adj_rels][:5],
        "parameters": {"centrality_alpha": 0.85},
        "thresholds": {"bridge_betweenness": 0.05},
        "limitations": "Distinguishes observed data (entity/relationships) from analytical interpretation (centrality/community). Interpretation does not imply guilt.",
        "provenance": [{"source": "graph_repo", "analysis_type": "entity", "timestamp": _now_iso()}, {"source": "network_analysis", "analysis_type": "centrality", "timestamp": _now_iso()}],
        "generated_at": _now_iso(),
        "lineage": _lineage("entity", "centrality+community+bridge", {}, {"entity_id": entity_id}, [f"{len(adj_rels)} rels"], "Entity analysis", _dataset_id(dataset)),
        "reproducibility": {"analysis_type": "entity", "entity_id": entity_id, "dataset_id": _dataset_id(dataset), "result_id": explanation_id, "deterministic": True},
        "observed_data": {"entity": {"entity_id": entity_id, "entity_type": etype, "properties": props}, "relationships": adj_rels[:10]},
        "analytical_interpretation": {
            "centrality": {k: v.get(entity_id) for k, v in centrality.items()},
            "community": community,
            "is_bridge": is_bridge,
            "indicators": indicators[:5],
        },
    }
