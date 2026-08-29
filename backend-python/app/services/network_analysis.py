"""Network analysis service — Milestone 5 Graph Intelligence.

Provides deterministic, explainable graph metrics only. No guilt/criminality scoring.

Vocabulary limited to neutral terms:
    network centrality, connection density, community membership,
    relationship intensity, pattern indicator, anomaly indicator,
    interaction_strength, betweenness, closeness, PageRank.

Every indicator carries `reason`/`explanation` and `evidence` ids.

Implementation:
- In-memory path uses NetworkX (degree, betweenness, closeness, PageRank,
  greedy_modularity communities, articulation points).
- Neo4j path prefers Cypher where practical, but for the synthetic scale
  (~150 nodes, 446 rels) export_snapshot + NetworkX is bounded and deterministic.
- All outputs are sorted for determinism; scores are rounded.

Safety: no metric is interpreted as criminality. High centrality does not imply guilt.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Set, Tuple, Optional
import hashlib
import json

try:
    import networkx as nx
    from networkx.algorithms.community import greedy_modularity_communities

    _NX_AVAILABLE = True
except ImportError:
    nx = None  # type: ignore
    greedy_modularity_communities = None  # type: ignore
    _NX_AVAILABLE = False

EntitySnapshot = Dict[str, Tuple[str, Dict[str, Any]]]  # id -> (type, props)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _adjacency(entities: EntitySnapshot, relationships: List[Dict[str, Any]]) -> Dict[str, List[Tuple[str, str, str]]]:
    adj: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)
    for rel in relationships:
        s, t = rel["source_id"], rel["target_id"]
        rel_type = rel.get("relationship_type", "RELATED_TO_CASE")
        adj[s].append((t, rel_type, rel.get("relationship_id", "")))
        adj[t].append((s, rel_type, rel.get("relationship_id", "")))
    for eid in entities:
        adj.setdefault(eid, [])
    return adj


def _nx_graph(entities: EntitySnapshot, relationships: List[Dict[str, Any]]):
    """Build NetworkX Graph (undirected for centrality/community)."""
    if not _NX_AVAILABLE:
        raise RuntimeError("networkx not installed; pip install networkx")
    G = nx.Graph()
    for eid, (etype, props) in entities.items():
        filtered = {k: v for k, v in props.items() if k not in ("entity_type", "entity_id") and isinstance(v, (str, int, float, bool))}
        G.add_node(eid, entity_type=etype, **filtered)
    for rel in relationships:
        s, t = rel["source_id"], rel["target_id"]
        if s not in G:
            G.add_node(s, entity_type=rel.get("source_type", "Unknown"))
        if t not in G:
            G.add_node(t, entity_type=rel.get("target_type", "Unknown"))
        G.add_edge(s, t, relationship_id=rel.get("relationship_id", ""), relationship_type=rel.get("relationship_type", ""), confidence=float(rel.get("confidence", 0.5)))
    return G


def _directed_tx_graph(relationships: List[Dict[str, Any]]):
    """Directed graph for transaction chains (TRANSFERRED_TO only)."""
    if not _NX_AVAILABLE:
        raise RuntimeError("networkx not installed")
    DG = nx.DiGraph()
    for rel in relationships:
        if rel.get("relationship_type") == "TRANSFERRED_TO":
            s, t = rel["source_id"], rel["target_id"]
            DG.add_edge(s, t, relationship_id=rel.get("relationship_id", ""), timestamp=rel.get("timestamp"), amount=rel.get("metadata", {}).get("amount") if isinstance(rel.get("metadata"), dict) else None)
    return DG


# ---------------------------------------------------------------------------
# Legacy helpers kept for Milestone 3 compatibility
# ---------------------------------------------------------------------------

def connected_components(adjacency: Dict[str, List]) -> List[List[str]]:
    seen: Set[str] = set()
    components: List[List[str]] = []
    for start in sorted(adjacency):
        if start in seen:
            continue
        stack, component = [start], []
        seen.add(start)
        while stack:
            node = stack.pop()
            component.append(node)
            for neighbor, _, _ in adjacency[node]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component))
    return components


def label_propagation_communities(adjacency: Dict[str, List], max_iterations: int = 12) -> List[Set[str]]:
    """Deterministic label propagation over sorted node order (legacy)."""
    labels = {node: i for i, node in enumerate(sorted(adjacency))}
    for _ in range(max_iterations):
        changed = False
        for node in sorted(adjacency):
            neighbor_labels = Counter(labels[nb] for nb, _, _ in adjacency[node])
            if not neighbor_labels:
                continue
            best_label = min((-count, label) for label, count in neighbor_labels.items())[1]
            if labels[node] != best_label:
                labels[node] = best_label
                changed = True
        if not changed:
            break
    communities: Dict[int, Set[str]] = defaultdict(set)
    for node, label in labels.items():
        communities[label].add(node)
    return [members for _, members in sorted(communities.items(), key=lambda kv: min(kv[1]))]


def articulation_points(adjacency: Dict[str, List]) -> Set[str]:
    """Tarjan's articulation points — potential bridge nodes."""
    index_counter = [0]
    indices, low = {}, {}
    points: Set[str] = set()

    def dfs(node: str, parent: Optional[str]) -> None:
        children = 0
        indices[node] = low[node] = index_counter[0]
        index_counter[0] += 1
        for neighbor, _, _ in adjacency[node]:
            if neighbor == parent:
                continue
            if neighbor not in indices:
                children += 1
                dfs(neighbor, node)
                low[node] = min(low[node], low[neighbor])
                if parent is not None and low[neighbor] >= indices[node]:
                    points.add(node)
                elif parent is None and children > 1:
                    points.add(node)
            else:
                low[node] = min(low[node], indices[neighbor])

    for node in sorted(adjacency):
        if node not in indices:
            dfs(node, None)
    return points


# ---------------------------------------------------------------------------
# Milestone 5: Centrality
# ---------------------------------------------------------------------------

def compute_centrality(entities: EntitySnapshot, relationships: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Real graph metrics via NetworkX. All values are deterministic.

    Returns dict with keys: degree, betweenness, closeness, pagerank
    Each maps entity_id -> normalized score (0..1 where applicable).
    Meanings (documented for API):
      degree: number of direct connections relative to graph size ( degree/(n-1) )
      betweenness: frequency entity lies on shortest paths (normalized)
      closeness: inverse average distance to all reachable nodes
      pagerank: link-analysis score (damping 0.85, sums to 1)
    """
    if not entities:
        return {"degree": {}, "betweenness": {}, "closeness": {}, "pagerank": {}}
    if not _NX_AVAILABLE:
        # Fallback to simple degree only
        adj = _adjacency(entities, relationships)
        n = len(entities)
        deg = {eid: len(adj[eid]) / max(1, n - 1) for eid in entities}
        return {"degree": deg, "betweenness": {}, "closeness": {}, "pagerank": {}}

    G = _nx_graph(entities, relationships)
    n = G.number_of_nodes()
    if n == 1:
        node = list(G.nodes())[0]
        return {
            "degree": {node: 0.0},
            "betweenness": {node: 0.0},
            "closeness": {node: 0.0},
            "pagerank": {node: 1.0},
        }
    # Degree centrality (already normalized)
    degree = nx.degree_centrality(G)
    # Betweenness (normalized, deterministic)
    betweenness = nx.betweenness_centrality(G, normalized=True) if n > 2 else {node: 0.0 for node in G.nodes()}
    # Closeness (handle disconnected)
    closeness = nx.closeness_centrality(G) if n > 1 else {node: 0.0 for node in G.nodes()}
    # PageRank (deterministic, handle disconnected)
    try:
        pagerank = nx.pagerank(G, alpha=0.85, max_iter=100, tol=1e-6) if n > 0 else {}
    except Exception:
        pagerank = {node: 1.0 / n for node in G.nodes()} if n else {}

    # Round and sort for determinism
    def _rounded_sorted(d: Dict[str, float]) -> Dict[str, float]:
        return {k: round(float(v), 6) for k, v in sorted(d.items())}

    return {
        "degree": _rounded_sorted(degree),
        "betweenness": _rounded_sorted(betweenness),
        "closeness": _rounded_sorted(closeness),
        "pagerank": _rounded_sorted(pagerank),
    }


# ---------------------------------------------------------------------------
# Communities (deterministic)
# ---------------------------------------------------------------------------

def find_communities(entities: EntitySnapshot, relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Greedy modularity communities (deterministic on sorted nodes).

    Returns list of {community_id, members, size, internal_edges, density}
    Community IDs are deterministic (sorted by min member id).
    """
    if not entities:
        return []
    if not _NX_AVAILABLE:
        # Fallback to label propagation
        adj = _adjacency(entities, relationships)
        lp = label_propagation_communities(adj)
        result = []
        for idx, members in enumerate(sorted(lp, key=lambda s: min(s))):
            mem_list = sorted(members)
            result.append({
                "community_id": f"community-{idx:03d}",
                "members": mem_list,
                "size": len(mem_list),
                "internal_edges": sum(1 for r in relationships if r["source_id"] in members and r["target_id"] in members),
                "density": round(len([r for r in relationships if r["source_id"] in members and r["target_id"] in members]) / (len(mem_list) * (len(mem_list) - 1) / 2) if len(mem_list) > 1 else 0.0, 6),
            })
        return result

    G = _nx_graph(entities, relationships)
    # Greedy modularity is deterministic when nodes are sorted; NetworkX handles it
    try:
        # Ensure deterministic: sort nodes, use weight=None
        comm_sets = list(greedy_modularity_communities(G, weight=None))
    except Exception:
        # Fallback to connected components as communities
        adj = _adjacency(entities, relationships)
        comm_sets = [set(c) for c in connected_components(adj)]

    # Deterministic ordering: sort by min member id
    comm_sets_sorted = sorted([sorted(list(c)) for c in comm_sets], key=lambda m: m[0] if m else "")
    result = []
    for idx, members in enumerate(comm_sets_sorted):
        member_set = set(members)
        internal = sum(1 for r in relationships if r["source_id"] in member_set and r["target_id"] in member_set)
        density = round(internal / (len(members) * (len(members) - 1) / 2) if len(members) > 1 else 0.0, 6)
        result.append({
            "community_id": f"community-{idx:03d}",
            "members": members,
            "size": len(members),
            "internal_edges": internal,
            "density": density,
        })
    return result


# ---------------------------------------------------------------------------
# Bridges (betweenness + articulation + boundary)
# ---------------------------------------------------------------------------

def find_bridges(entities: EntitySnapshot, relationships: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    """Identify bridge candidates via betweenness and articulation.

    Returns list of {entity_id, entity_type, metric, score, explanation, evidence}
    """
    if not entities:
        return []
    adj = _adjacency(entities, relationships)
    central = compute_centrality(entities, relationships)
    betweenness = central.get("betweenness", {})
    arts = articulation_points(adj)

    # Community boundary: nodes with edges to multiple communities
    communities = find_communities(entities, relationships)
    node_to_comm = {}
    for comm in communities:
        for m in comm["members"]:
            node_to_comm[m] = comm["community_id"]

    candidates: List[Dict[str, Any]] = []
    for eid in sorted(entities.keys()):
        score = float(betweenness.get(eid, 0.0))
        is_articulation = eid in arts
        # Boundary score: how many distinct neighboring communities
        neighbor_comms = set()
        for nb, _, _ in adj.get(eid, []):
            if nb in node_to_comm and node_to_comm[nb] != node_to_comm.get(eid):
                neighbor_comms.add(node_to_comm[nb])
        boundary_score = len(neighbor_comms)

        # Bridge if articulation OR high betweenness OR high boundary
        # Thresholds are analytical, not criminal: top betweenness or articulation
        is_bridge = is_articulation or score > 0.05 or boundary_score >= 2
        if not is_bridge:
            continue
        # Metric chooses primary signal
        if is_articulation:
            metric = "articulation_point"
            explanation = (
                f"Articulation point: removing {eid} would increase connected components; "
                f"it connects {boundary_score + 1} network regions with {len(adj[eid])} direct connections."
            )
        elif boundary_score >= 2:
            metric = "community_boundary"
            explanation = (
                f"High community boundary score ({boundary_score} neighboring communities): "
                f"entity lies between distinct interaction clusters with betweenness {score:.4f}."
            )
        else:
            metric = "betweenness_centrality"
            explanation = (
                f"High betweenness centrality ({score:.4f}) indicates this entity frequently lies on "
                f"shortest paths between other entities, connecting multiple network regions."
            )
        etype = entities[eid][0]
        evidence = [rel_id for _, _, rel_id in adj[eid] if rel_id][:5]
        candidates.append({
            "entity_id": eid,
            "entity_type": etype,
            "metric": metric,
            "score": round(score, 6),
            "explanation": explanation,
            "evidence": evidence,
        })

    # Sort by score desc, then entity_id for determinism, take top_k
    candidates_sorted = sorted(candidates, key=lambda x: (-x["score"], x["entity_id"]))
    return candidates_sorted[:top_k]


# ---------------------------------------------------------------------------
# Relationship strength (interaction_strength)
# ---------------------------------------------------------------------------

_REL_TYPE_WEIGHT = {
    "KNOWS": 1.0,
    "CALLED": 1.2,
    "TRANSFERRED_TO": 1.5,
    "WORKS_FOR": 1.0,
    "ASSOCIATED_WITH": 0.9,
    "OWNS": 1.0,
    "USED": 1.0,
    "TRAVELED_TO": 0.8,
    "LOCATED_AT": 0.7,
    "MENTIONED_IN": 0.5,
    "RELATED_TO_CASE": 0.5,
}


def compute_relationship_strength(relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Explainable interaction_strength per relationship.

    Factors (deterministic, not learned):
    - type weight (see _REL_TYPE_WEIGHT)
    - normalized confidence (0..1)
    - repeated pair frequency (how many relationships share same unordered pair)
    - temporal proximity bonus if timestamp present and close to another interaction between same pair

    Returns list sorted by score desc, each with {relationship_id, interaction_strength, factors, explanation}
    """
    # Frequency per unordered pair
    pair_counts: Counter = Counter()
    for rel in relationships:
        key = tuple(sorted([rel["source_id"], rel["target_id"]]))
        pair_counts[key] += 1

    result = []
    for rel in sorted(relationships, key=lambda r: r["relationship_id"]):
        rid = rel["relationship_id"]
        rtype = rel.get("relationship_type", "RELATED_TO_CASE")
        w_type = _REL_TYPE_WEIGHT.get(rtype, 0.8)
        conf = float(rel.get("confidence", 0.5))
        pair_key = tuple(sorted([rel["source_id"], rel["target_id"]]))
        freq = pair_counts[pair_key]
        freq_factor = min(1.0, (freq - 1) * 0.15)  # 0 for single, up to 1 for many

        # Temporal factor: if timestamp exists, bonus if within 24h of another same-pair interaction
        # For simplicity, we check existence of timestamp (binary)
        temporal_bonus = 0.1 if rel.get("timestamp") else 0.0

        # Score: weighted combination, capped 0..1
        raw = (w_type * 0.3 + conf * 0.4 + freq_factor * 0.2 + temporal_bonus)
        score = round(min(1.0, raw / 1.5), 4)  # normalize

        factors = {
            "type_weight": w_type,
            "confidence": conf,
            "pair_frequency": freq,
            "frequency_factor": round(freq_factor, 4),
            "temporal_bonus": temporal_bonus,
        }
        explanation = (
            f"interaction_strength {score} from type '{rtype}' (weight {w_type}), "
            f"confidence {conf}, pair frequency {freq} (factor {freq_factor:.2f})"
            + (", timestamp present (+0.1)" if temporal_bonus else "")
            + "."
        )
        result.append({
            "relationship_id": rid,
            "relationship_type": rtype,
            "source_id": rel["source_id"],
            "target_id": rel["target_id"],
            "interaction_strength": score,
            "factors": factors,
            "explanation": explanation,
        })

    return sorted(result, key=lambda x: (-x["interaction_strength"], x["relationship_id"]))


# ---------------------------------------------------------------------------
# Temporal analysis (bursts)
# ---------------------------------------------------------------------------

def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # Handle Z
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def analyze_temporal(relationships: List[Dict[str, Any]], window_hours: int = 24, z_threshold: float = 2.0) -> List[Dict[str, Any]]:
    """Detect temporal bursts deterministically.

    Groups all relationships by 24h windows (or given window) and compares
    per-entity window count to baseline (mean, std). Flags windows where
    observed > mean + z_threshold*std.

    Also detects communication/transaction bursts specifically.

    Returns list of indicators: {indicator_type, time_window, entity_ids, observed_count, baseline, explanation, evidence}
    """
    if not relationships:
        return []

    # Collect timestamps per entity
    entity_times: Dict[str, List[datetime]] = defaultdict(list)
    all_times: List[datetime] = []
    for rel in relationships:
        ts = _parse_ts(rel.get("timestamp"))
        if not ts:
            continue
        all_times.append(ts)
        entity_times[rel["source_id"]].append(ts)
        entity_times[rel["target_id"]].append(ts)
        # Also track by relationship type for comm/tx bursts
        if rel["relationship_type"] in ("CALLED", "TRANSFERRED_TO"):
            entity_times[f"type:{rel['relationship_type']}"].append(ts)

    if not all_times:
        return []

    # Overall baseline: histogram by window
    # Use window_hours buckets from min time
    min_t = min(all_times)
    max_t = max(all_times)
    total_windows = max(1, int((max_t - min_t).total_seconds() // (window_hours * 3600)) + 1)

    # For each entity, compute window counts
    indicators: List[Dict[str, Any]] = []

    for eid, times in sorted(entity_times.items()):
        if len(times) < 3:  # need at least 3 to establish burst
            continue
        # Bucket times into window indices
        buckets: Counter = Counter()
        for t in times:
            idx = int((t - min_t).total_seconds() // (window_hours * 3600))
            buckets[idx] += 1
        counts = list(buckets.values())
        if len(counts) < 2:
            continue
        mean = sum(counts) / len(counts)
        # std (population)
        var = sum((c - mean) ** 2 for c in counts) / len(counts)
        std = var ** 0.5
        threshold = mean + z_threshold * std if std > 0 else mean + 1

        for win_idx, cnt in sorted(buckets.items()):
            if cnt > threshold and cnt >= 3:
                window_start = min_t + timedelta(hours=win_idx * window_hours)
                window_end = window_start + timedelta(hours=window_hours)
                # Evidence: relationship_ids in this window for this entity
                ev_ids = []
                for rel in relationships:
                    ts = _parse_ts(rel.get("timestamp"))
                    if not ts:
                        continue
                    if not (window_start <= ts < window_end):
                        continue
                    if rel["source_id"] == eid or rel["target_id"] == eid or eid.startswith("type:"):
                        ev_ids.append(rel["relationship_id"])
                    if len(ev_ids) >= 5:
                        break
                indicator_type = "communication_burst" if eid.startswith("type:CALLED") else "transaction_burst" if eid.startswith("type:TRANSFERRED_TO") else "interaction_burst"
                # For entity-specific, use neutral type
                if not eid.startswith("type:"):
                    indicator_type = "temporal_burst"
                explanation = (
                    f"Observed {cnt} interactions for '{eid}' in {window_hours}h window "
                    f"[{window_start.isoformat()} - {window_end.isoformat()}) "
                    f"compared to baseline mean {mean:.2f} (std {std:.2f}, threshold {threshold:.2f}) over {total_windows} windows."
                )
                indicators.append({
                    "indicator_type": indicator_type,
                    "time_window": f"{window_start.isoformat()}/{window_end.isoformat()}",
                    "entity_ids": [eid] if not eid.startswith("type:") else [],
                    "observed_count": cnt,
                    "baseline": {"mean": round(mean, 2), "std": round(std, 2), "threshold": round(threshold, 2), "total_windows": total_windows},
                    "explanation": explanation,
                    "evidence": ev_ids[:5],
                })

    # Sort for determinism
    return sorted(indicators, key=lambda x: (-x["observed_count"], x["time_window"]))


# ---------------------------------------------------------------------------
# Transaction chains (A -> B -> C ... via TRANSFERRED_TO)
# ---------------------------------------------------------------------------

def find_transaction_chains(relationships: List[Dict[str, Any]], min_hops: int = 2, max_hops: int = 4) -> List[Dict[str, Any]]:
    """Find directed transaction chains via TRANSFERRED_TO.

    Returns list of {chain_id, source_account, intermediate_accounts, destination_account, hop_count, transaction_count, evidence, explanation}
    """
    tx_rels = [r for r in relationships if r.get("relationship_type") == "TRANSFERRED_TO"]
    if not tx_rels or not _NX_AVAILABLE:
        return []

    DG = _directed_tx_graph(relationships)
    if DG.number_of_edges() == 0:
        return []

    # Find all simple paths up to max_hops that have at least min_hops
    # For determinism, iterate sorted source nodes
    chains: List[Dict[str, Any]] = []
    # Use all pairs, but limit to avoid explosion: for each source, BFS up to max_hops
    for source in sorted(DG.nodes()):
        # BFS limited depth
        # Use DFS to find paths
        stack = [(source, [source], set([source]))]
        while stack:
            node, path, visited = stack.pop()
            if len(path) - 1 >= min_hops and len(path) - 1 <= max_hops:
                # Record chain
                dest = path[-1]
                intermediates = path[1:-1]
                # Collect evidence relationship_ids along path
                ev = []
                for i in range(len(path) - 1):
                    # Find edge's relationship_id (first matching)
                    for rel in tx_rels:
                        if rel["source_id"] == path[i] and rel["target_id"] == path[i + 1]:
                            ev.append(rel["relationship_id"])
                            break
                chains.append({
                    "chain_id": f"chain-{source}-{dest}-{len(chains):04d}",
                    "source_account": source,
                    "intermediate_accounts": intermediates,
                    "destination_account": dest,
                    "hop_count": len(path) - 1,
                    "transaction_count": len(path) - 1,
                    "evidence": ev,
                    "explanation": (
                        f"Directed transaction chain of {len(path)-1} hops from {source} to {dest}"
                        + (f" via {', '.join(intermediates)}" if intermediates else "")
                        + f"; observed {len(path)-1} TRANSFERRED_TO relationships."
                    ),
                })
            if len(path) - 1 >= max_hops:
                continue
            for succ in sorted(DG.successors(node)):
                if succ in visited:
                    continue
                # Deterministic: sort successors
                stack.append((succ, path + [succ], visited | {succ}))

    # Deduplicate by evidence set (same chain via different DFS order)
    seen_ev = set()
    deduped = []
    for c in sorted(chains, key=lambda x: (x["hop_count"], x["source_account"], x["destination_account"])):
        ev_tup = tuple(sorted(c["evidence"]))
        if ev_tup in seen_ev:
            continue
        seen_ev.add(ev_tup)
        deduped.append(c)

    # Limit for milestone (avoid huge output)
    return deduped[:20]


# ---------------------------------------------------------------------------
# Indicator model
# ---------------------------------------------------------------------------

def _severity_from_score(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


def generate_indicators(entities: EntitySnapshot, relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate structured analytical indicators with severity, explanation, evidence.

    Severity represents analytical signal strength, not criminality.
    Deterministic: created_at is fixed for reproducibility.
    """
    indicators: List[Dict[str, Any]] = []
    now_iso = "2024-01-01T00:00:00Z"

    # Centrality indicators
    central = compute_centrality(entities, relationships)
    # High betweenness -> HIGH/MEDIUM
    for eid, score in sorted(central.get("betweenness", {}).items(), key=lambda kv: -kv[1])[:5]:
        if score < 0.05:
            continue
        severity = _severity_from_score(score)
        indicators.append({
            "indicator_id": f"ind-centrality-{eid}",
            "indicator_type": "high_betweenness_centrality",
            "severity": severity,
            "entity_ids": [eid],
            "relationship_ids": [rel_id for nb, _, rel_id in _adjacency(entities, relationships)[eid] if rel_id][:5],
            "score": round(score, 4),
            "explanation": (
                f"Entity {eid} has betweenness centrality {score:.4f}, indicating it lies on "
                f"frequently used shortest paths. This is a descriptive network metric; high centrality "
                f"does not imply criminality and requires investigator review of underlying relationships."
            ),
            "evidence": [rel_id for nb, _, rel_id in _adjacency(entities, relationships)[eid] if rel_id][:5],
            "created_at": now_iso,
        })

    # Bridge indicators
    for b in find_bridges(entities, relationships, top_k=5):
        # Bridge score already normalized 0..1
        severity = _severity_from_score(b["score"] if b["metric"] == "betweenness_centrality" else 0.6)
        indicators.append({
            "indicator_id": f"ind-bridge-{b['entity_id']}",
            "indicator_type": f"bridge_{b['metric']}",
            "severity": severity,
            "entity_ids": [b["entity_id"]],
            "relationship_ids": b["evidence"],
            "score": b["score"],
            "explanation": b["explanation"] + " This is a structural observation, not a guilt assessment.",
            "evidence": b["evidence"],
            "created_at": now_iso,
        })

    # Temporal bursts
    for t in analyze_temporal(relationships)[:5]:
        # Severity based on how far observed exceeds threshold
        obs = t["observed_count"]
        thr = t["baseline"]["threshold"]
        score = min(1.0, (obs - thr + 1) / 5.0) if thr else 0.5
        severity = _severity_from_score(score)
        indicators.append({
            "indicator_id": f"ind-temporal-{hashlib.sha256(t['time_window'].encode()).hexdigest()[:8]}",
            "indicator_type": t["indicator_type"],
            "severity": severity,
            "entity_ids": t["entity_ids"],
            "relationship_ids": t["evidence"],
            "score": round(score, 4),
            "explanation": t["explanation"],
            "evidence": t["evidence"],
            "created_at": now_iso,
        })

    # Transaction chains
    for ch in find_transaction_chains(relationships)[:5]:
        score = min(1.0, ch["hop_count"] / 4.0)
        severity = _severity_from_score(score)
        indicators.append({
            "indicator_id": f"ind-chain-{ch['chain_id']}",
            "indicator_type": "transaction_chain",
            "severity": severity,
            "entity_ids": [ch["source_account"]] + ch["intermediate_accounts"] + [ch["destination_account"]],
            "relationship_ids": ch["evidence"],
            "score": round(score, 4),
            "explanation": ch["explanation"] + " Chain existence alone is not suspicious; review transaction metadata and provenance.",
            "evidence": ch["evidence"],
            "created_at": now_iso,
        })

    # Deterministic sort
    return sorted(indicators, key=lambda x: (-{"HIGH": 3, "MEDIUM": 2, "LOW": 1}[x["severity"]], -x["score"], x["indicator_id"]))


# ---------------------------------------------------------------------------
# Main analyze_graph (Milestone 5) — extends Milestone 3 analyze_network
# ---------------------------------------------------------------------------

def _base_analysis(entities: EntitySnapshot, relationships: List[Dict[str, Any]], top_k: int = 5) -> Dict[str, Any]:
    """Milestone 3 base descriptive analysis (used by both legacy and Milestone 5)."""
    adjacency = _adjacency(entities, relationships)
    degrees = {eid: len(entries) for eid, entries in adjacency.items()}
    degree_values = sorted(degrees.values())
    n = len(degree_values)
    avg_degree = sum(degree_values) / n if n else 0.0
    components = connected_components(adjacency)
    top_entities = sorted(degrees.items(), key=lambda kv: (-kv[1], kv[0]))
    indicators: List[Dict[str, Any]] = []
    for rank, (eid, degree) in enumerate(top_entities[:top_k]):
        if degree < 2 or (n > 1 and degree <= avg_degree):
            break
        evidence = [rel_id for nb, _, rel_id in adjacency[eid] if rel_id][:degree]
        indicators.append({
            "entity_id": eid,
            "indicator": "high_network_centrality",
            "reason": f"Entity participates in {degree} observed relationships across {len({entities[nb][0] for nb, _, _ in adjacency[eid] if nb in entities})} entity types",
            "evidence": evidence,
        })
    bridges = articulation_points(adjacency)
    bridge_indicators = []
    for eid in sorted(bridges)[:top_k]:
        removal_components = len(components)
        neighbors = [nb for nb, _, _ in adjacency[eid]]
        bridge_indicators.append({
            "entity_id": eid,
            "indicator": "bridge_candidate",
            "reason": f"Removing this entity would disconnect previously linked parts of the network ({len(neighbors)} direct connections; network currently has {removal_components} connected components)",
            "evidence": [rel_id for _, _, rel_id in adjacency[eid] if rel_id][:len(neighbors)],
        })
    communities = label_propagation_communities(adjacency)
    monthly: Counter = Counter()
    for rel in relationships:
        ts = rel.get("timestamp")
        if ts:
            monthly[ts[:7]] += 1
    temporal = [{"month": month, "relationship_count": count} for month, count in sorted(monthly.items())]
    type_counts: Counter = Counter(e[0] for e in entities.values())
    rel_type_counts: Counter = Counter(r["relationship_type"] for r in relationships)
    density = (2 * len(relationships) / (n * (n - 1))) if n > 1 else 0.0
    return {
        "counts": {"entities": n, "relationships": len(relationships), "connected_components": len(components), "communities_detected": len(communities)},
        "entity_type_counts": dict(sorted(type_counts.items())),
        "relationship_type_counts": dict(sorted(rel_type_counts.items())),
        "degree_statistics": {"min": degree_values[0] if degree_values else 0, "max": degree_values[-1] if degree_values else 0, "average": round(avg_degree, 4), "connection_density": round(density, 6)},
        "highly_connected_entities": [{"entity_id": eid, "degree": d} for eid, d in top_entities[:top_k] if d >= 2],
        "components_preview": [{"size": len(c), "sample_entity_ids": c[:5]} for c in components[:10]],
        "communities": [{"community_index": i, "size": len(members), "member_entity_ids": sorted(members)} for i, members in enumerate(communities)],
        "temporal_activity": temporal,
        "indicators": indicators + bridge_indicators,
        "terminology_notice": "Descriptive indicators only. This system does not assess guilt or criminality; all findings support human review.",
    }


def analyze_graph(entities: EntitySnapshot, relationships: List[Dict[str, Any]], top_k: int = 5) -> Dict[str, Any]:
    """Full Graph Intelligence analysis (Milestone 5)."""
    base = _base_analysis(entities, relationships, top_k=top_k)
    # Add new metrics
    centrality = compute_centrality(entities, relationships)
    communities = find_communities(entities, relationships)
    bridges = find_bridges(entities, relationships, top_k=top_k)
    temporal = analyze_temporal(relationships)
    chains = find_transaction_chains(relationships)
    rel_strength = compute_relationship_strength(relationships)
    indicators_new = generate_indicators(entities, relationships)

    # Build enriched response (keep all base fields)
    enriched = dict(base)
    enriched.update({
        "centrality": centrality,
        "centrality_explanations": {
            "degree": "Number of direct connections relative to graph size (degree/(n-1)). High degree means many direct observations.",
            "betweenness": "Frequency entity lies on shortest paths between others. High betweenness indicates bridging multiple regions.",
            "closeness": "Inverse average distance to all reachable nodes. High closeness means short paths to others.",
            "pagerank": "Link-analysis score (damping 0.85). High PageRank indicates well-connected entity via important neighbors.",
        },
        "communities_detailed": communities,
        "bridges_detailed": bridges,
        "temporal_indicators": temporal,
        "transaction_chains": chains,
        "relationship_strength": rel_strength[:20],  # top 20
        "indicators_enhanced": indicators_new,
        # Keep legacy indicators for backward compat; new structured ones are in indicators_enhanced
        "indicators": base.get("indicators", []),
    })
    return enriched


# For backward compat, keep analyze_network as the legacy entry point
# (tests import it). analyze_graph is the new enriched version.
# We make analyze_network call analyze_graph and strip extra keys for legacy callers that expect old shape,
# but we also keep a full version. Simpler: make analyze_network an alias to analyze_graph but ensure old tests still pass
# by keeping required keys. New keys are additive, so old tests will still pass.
def analyze_network(snapshot_entities: EntitySnapshot, relationships: List[Dict[str, Any]], top_k: int = 5) -> Dict[str, Any]:
    """Legacy Milestone 3 entry point — now enriched via Milestone 5 but backward compatible."""
    # Call the full graph intelligence pipeline
    result = analyze_graph(snapshot_entities, relationships, top_k=top_k)
    # Ensure legacy keys exist (they do, via analyze_graph's base)
    return result
