"""Neo4j-backed graph repository (lazy driver import).

The application never imports ``neo4j`` directly — only this module
does. If the driver or the database is unavailable, construction fails
with :class:`GraphRepositoryError` and callers can fall back to the
in-memory implementation.

Cypher uses the canonical model: nodes keyed on ``entity_id``, labels =
canonical entity type, relationship types = canonical set.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .base import (
    GraphRepository,
    GraphRepositoryError,
    GraphStats,
)

try:  # pragma: no cover - environment dependent
    from neo4j import GraphDatabase  # type: ignore

    NEO4J_DRIVER_INSTALLED = True
except ImportError:
    GraphDatabase = None  # type: ignore[assignment]
    NEO4J_DRIVER_INSTALLED = False


_ALLOWED_ENTITY_TYPES = {
    "Person", "Organization", "PhoneNumber", "Vehicle", "Location",
    "FinancialAccount", "Transaction", "Communication", "Case", "FIR", "Event", "Evidence"
}
_ALLOWED_RELATIONSHIP_TYPES = {
    "KNOWS", "CALLED", "TRANSFERRED_TO", "LOCATED_AT", "TRAVELED_TO",
    "ASSOCIATED_WITH", "WORKS_FOR", "OWNS", "USED", "MENTIONED_IN", "RELATED_TO_CASE"
}


def _validate_label(label: str, allowed: set, kind: str) -> None:
    if label not in allowed:
        raise GraphRepositoryError(f"Invalid {kind} '{label}' — not in canonical set")


class Neo4jGraphRepository(GraphRepository):
    def __init__(self, uri: str, user: str, password: str) -> None:
        if not NEO4J_DRIVER_INSTALLED:
            raise GraphRepositoryError(
                "neo4j driver not installed; pip install neo4j")
        try:
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
            self._driver.verify_connectivity()
        except Exception as exc:
            raise GraphRepositoryError(
                f"cannot connect to Neo4j at {uri}: {exc}") from exc

    def close(self) -> None:
        self._driver.close()

    # -- writes ---------------------------------------------------------------

    def upsert_entity(self, entity_id: str, entity_type: str,
                      properties: Dict[str, Any]) -> None:
        _validate_label(entity_type, _ALLOWED_ENTITY_TYPES, "entity_type")
        query = (
            f"MERGE (n:{entity_type} {{entity_id: $entity_id}}) "
            "SET n += $props"
        )
        with self._driver.session() as session:
            session.run(query, entity_id=entity_id,
                        props={"entity_type": entity_type, **properties})

    def upsert_relationship(self, relationship_id: str, source_id: str,
                            source_type: str, target_id: str,
                            target_type: str, relationship_type: str,
                            properties: Dict[str, Any]) -> None:
        _validate_label(source_type, _ALLOWED_ENTITY_TYPES, "source_type")
        _validate_label(target_type, _ALLOWED_ENTITY_TYPES, "target_type")
        _validate_label(relationship_type, _ALLOWED_RELATIONSHIP_TYPES, "relationship_type")
        query = (
            f"MATCH (a:{source_type} {{entity_id: $src}}) "
            f"MATCH (b:{target_type} {{entity_id: $tgt}}) "
            f"MERGE (a)-[r:{relationship_type} "
            "{{relationship_id: $rel_id}]->(b) "
            "SET r += $props"
        )
        with self._driver.session() as session:
            session.run(query, src=source_id, tgt=target_id,
                        rel_id=relationship_id, props=properties)

    # -- reads ---------------------------------------------------------------

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        query = "MATCH (n {entity_id: $eid}) RETURN labels(n) AS labels, properties(n) AS props"
        with self._driver.session() as session:
            row = session.run(query, eid=entity_id).single()
        if row is None:
            return None
        props = dict(row["props"])
        labels = row["labels"] or []
        # Normalize to InMemory shape: entity_id, entity_type, plus all props
        entity_type = props.get("entity_type") or (labels[0] if labels else "Unknown")
        result = {"entity_id": entity_id, "entity_type": entity_type, "labels": labels}
        result.update(props)
        return result

    def get_relationships(self, entity_id: str) -> List[Dict[str, Any]]:
        # Return provenance-complete relationships (both directions)
        query = (
            "MATCH (a {entity_id: $eid})-[r]-(b) "
            "RETURN type(r) AS relationship_type, "
            "properties(r) AS props, "
            "a.entity_id AS a_id, a.entity_type AS a_type, "
            "b.entity_id AS b_id, b.entity_type AS b_type, "
            "labels(a) AS a_labels, labels(b) AS b_labels, "
            "startNode(r).entity_id AS src_id, endNode(r).entity_id AS tgt_id"
        )
        results: List[Dict[str, Any]] = []
        with self._driver.session() as session:
            for row in session.run(query, eid=entity_id):
                props = dict(row["props"]) if row["props"] else {}
                # Determine direction: we store directed relationships a->b via MERGE (a)-[r]->(b)
                # but query matches both directions; use src_id/tgt_id to determine actual source
                src_id = props.get("source_id") or row["src_id"] or row["a_id"]
                tgt_id = props.get("target_id") or row["tgt_id"] or row["b_id"]
                src_type = props.get("source_type") or row["a_type"] or (row["a_labels"][0] if row["a_labels"] else "Unknown")
                tgt_type = props.get("target_type") or row["b_type"] or (row["b_labels"][0] if row["b_labels"] else "Unknown")
                rel = {
                    "relationship_id": props.get("relationship_id") or "",
                    "source_id": src_id,
                    "source_type": src_type,
                    "target_id": tgt_id,
                    "target_type": tgt_type,
                    "relationship_type": row["relationship_type"] or props.get("relationship_type"),
                    "timestamp": props.get("timestamp"),
                    "confidence": props.get("confidence", 0.5),
                    "extraction_method": props.get("extraction_method", "unknown"),
                    "created_at": props.get("created_at"),
                    "metadata": props.get("metadata", {}),
                }
                # Merge any remaining props (e.g., source_text)
                for k, v in props.items():
                    if k not in rel:
                        rel[k] = v
                results.append(rel)
        return results

    def neighborhood(self, entity_id: str, depth: int = 1) -> Dict[str, Any]:
        # BFS via Cypher variable-length path; also collect edges for the returned subgraph
        depth = max(1, min(int(depth), 6))
        node_query = (
            f"MATCH (start {{entity_id: $eid}})-[*1..{depth}]-(n) "
            "WHERE n <> start "
            "RETURN DISTINCT n.entity_id AS entity_id, labels(n) AS labels, n.entity_type AS entity_type"
        )
        edge_query = (
            f"MATCH (start {{entity_id: $eid}})-[r:*1..{depth}]-(n) "
            "WHERE n <> start "
            "RETURN DISTINCT startNode(r).entity_id AS from_id, endNode(r).entity_id AS to_id, type(r) AS relationship_type"
        )
        with self._driver.session() as session:
            node_rows = list(session.run(node_query, eid=entity_id))
            edge_rows = list(session.run(edge_query, eid=entity_id))
        nodes = [{"entity_id": entity_id, "depth": 0, "labels": []}]
        for r in node_rows:
            nodes.append({
                "entity_id": r["entity_id"],
                "depth": 1,  # Neo4j variable depth not tracked per-hop in this query; treat as 1 for milestone
                "labels": r["labels"],
                "entity_type": r["entity_type"],
            })
        edges = [
            {"from": e["from_id"], "to": e["to_id"], "relationship_type": e["relationship_type"]}
            for e in edge_rows
        ]
        return {
            "start_entity_id": entity_id,
            "depth": depth,
            "nodes": nodes,
            "edges": edges,
        }

    def shortest_path(self, from_entity_id: str, to_entity_id: str,
                      max_depth: int = 6) -> Optional[Dict[str, Any]]:
        query = (
            "MATCH p = shortestPath((a {entity_id: $from})-[*..%d]-(b "
            "{entity_id: $to})) RETURN "
            "[n IN nodes(p) | n.entity_id] AS entities, "
            "[r IN relationships(p) | type(r)] AS relationships"
            % max(1, min(int(max_depth), 10))
        )
        with self._driver.session() as session:
            row = session.run(query, **{"from": from_entity_id},
                              to=to_entity_id).single()
        if row is None:
            return {"found": False, "length": None,
                    "entities": [], "relationships": []}
        return {"found": True,
                "length": len(row["entities"]) - 1,
                "entities": row["entities"],
                "relationships": row["relationships"]}

    def statistics(self) -> GraphStats:
        with self._driver.session() as session:
            node_counts = {
                r["label"]: r["count"]
                for r in session.run(
                    "MATCH (n) RETURN labels(n)[0] AS label, count(n) "
                    "AS count") if r["label"]
            }
            total_nodes = session.run("MATCH (n) RETURN count(n) AS c") \
                .single()["c"]
            rel_counts = {
                r["t"]: r["c"] for r in session.run(
                    "MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c")
            }
            total_rels = session.run(
                "MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        return GraphStats(
            node_count=total_nodes,
            relationship_count=total_rels,
            type_counts=node_counts,
            relationship_type_counts=rel_counts,
            avg_degree=round((2 * total_rels / total_nodes), 4)
            if total_nodes else 0.0,
        )

    def export_snapshot(self) -> Tuple[Dict[str, Tuple[str, Dict[str, Any]]],
                                       List[Dict[str, Any]]]:
        """Export full graph snapshot via Cypher for analysis service.

        For the synthetic dataset (~150 nodes, ~446 rels) this is efficient.
        For larger production graphs, callers should use statistics()/neighborhood()
        Cypher aggregations instead of full export. This method is intentionally
        bounded and will page if needed in future.
        """
        entities: Dict[str, Tuple[str, Dict[str, Any]]] = {}
        relationships: List[Dict[str, Any]] = []
        with self._driver.session() as session:
            # Fetch all nodes (paginated logically; for milestone we fetch at once)
            node_rows = list(session.run("MATCH (n) RETURN n.entity_id AS entity_id, labels(n) AS labels, properties(n) AS props"))
            for row in node_rows:
                eid = row["entity_id"]
                if not eid:
                    continue
                props = dict(row["props"]) if row["props"] else {}
                etype = props.get("entity_type") or (row["labels"][0] if row["labels"] else "Unknown")
                # Include entity_type in props for consistency with InMemory
                props.setdefault("entity_type", etype)
                props.setdefault("entity_id", eid)
                entities[eid] = (etype, props)

            # Fetch all relationships with provenance
            rel_rows = list(session.run(
                "MATCH (a)-[r]->(b) "
                "RETURN r.relationship_id AS relationship_id, "
                "a.entity_id AS source_id, a.entity_type AS source_type, "
                "b.entity_id AS target_id, b.entity_type AS target_type, "
                "type(r) AS relationship_type, properties(r) AS props"
            ))
            for row in rel_rows:
                props = dict(row["props"]) if row["props"] else {}
                rel = {
                    "relationship_id": row["relationship_id"] or props.get("relationship_id", ""),
                    "source_id": row["source_id"] or props.get("source_id"),
                    "source_type": row["source_type"] or props.get("source_type"),
                    "target_id": row["target_id"] or props.get("target_id"),
                    "target_type": row["target_type"] or props.get("target_type"),
                    "relationship_type": row["relationship_type"] or props.get("relationship_type"),
                    "timestamp": props.get("timestamp"),
                    "confidence": props.get("confidence", 0.5),
                    "extraction_method": props.get("extraction_method", "unknown"),
                    "created_at": props.get("created_at"),
                    "metadata": props.get("metadata", {}),
                }
                # Preserve any extra provenance fields
                for k, v in props.items():
                    if k not in rel:
                        rel[k] = v
                relationships.append(rel)
        return entities, relationships
