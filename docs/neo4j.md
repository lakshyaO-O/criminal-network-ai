# Neo4j — Analytical Graph Projection (Milestone 4)

Neo4j is the **relationship/network projection** of the canonical PostgreSQL store, not the source of truth.

```
PostgreSQL (canonical) --pipeline sync--> Neo4j (projection) --Cypher--> /api/analysis, /api/network, /api/entities/{id}/neighborhood
```

## Abstraction

`backend-python/app/graph/base.py` `GraphRepository` (ABC):

- `upsert_entity(entity_id, entity_type, properties)`
- `upsert_relationship(relationship_id, source_id, source_type, target_id, target_type, relationship_type, properties)`
- `get_entity(entity_id) -> Optional[Dict]`
- `get_relationships(entity_id) -> List[Dict]`
- `neighborhood(entity_id, depth=1..6) -> {nodes, edges}`
- `shortest_path(from, to, max_depth=6) -> {found, length, entities, relationships}`
- `statistics() -> GraphStats`
- `export_snapshot() -> (entities, relationships)` (now implemented for Neo4j; for large graphs use aggregations)

Implementations:

- `app/graph/memory.py` `InMemoryGraphRepository` — dicts + BFS, `export_snapshot()` in-memory.
- `app/graph/neo4j_repo.py` `Neo4jGraphRepository` — lazy `neo4j` driver import; Cypher.

## Neo4j Details

- Image: `neo4j:5.24-community` (docker-compose, ports 7474/7687, `NEO4J_AUTH=neo4j/password`, healthcheck `cypher-shell RETURN 1`).
- Env: `APP_NEO4J_URI=bolt://localhost:7687` (docker: `bolt://neo4j:7687`), `APP_NEO4J_USER`, `APP_NEO4J_PASSWORD`, `NEO4J_ENABLED=true`.
- Nodes: `MERGE (n:{entity_type} {entity_id: $entity_id}) SET n += $props` (labels = canonical type, key = `entity_id`).
- Relationships: `MATCH (a:{source_type} {entity_id: $src}) MATCH (b:{target_type} {entity_id: $tgt}) MERGE (a)-[r:{relationship_type} {relationship_id: $rel_id}]->(b) SET r += $props` (all provenance preserved).
- Reads: `get_entity` via `MATCH (n {entity_id}) RETURN labels, properties`; `get_relationships` via `MATCH (a {entity_id})-[r]-(b)` returning `relationship_type, properties, source/target ids/types`; `neighborhood` via `-[*1..depth]-` with nodes+edges; `shortest_path` via `shortestPath`; `statistics` via `MATCH (n) RETURN labels...` and `MATCH ()-[r]->() RETURN type...`; `export_snapshot` via `MATCH (n)` + `MATCH ()-[r]->()` (bounded; for synthetic ~150 nodes/446 rels).
- All queries are parameterized Cypher, not string-concatenated user input.

## Persistence vs Graph Responsibility

| Concern | Store | Why |
|---|---|---|
| Canonical structured records (persons, cases, evidence, provenance) | PostgreSQL | Enforces CHECKs, FKs, ACID, TEXT IDs, audit |
| Relationship traversal, community/centrality, pathfinding | Neo4j | Native graph engine, Cypher |
| Unit tests, local dev without Docker | In-memory | No services required |

Pipeline (`ai/pipeline.py`) does `persist()` → PostgreSQL and `sync_graph()` → Neo4j separately; `do_persist`/`do_sync` flags allow testing stages independently. `GET /api/analysis` uses `graph_repo.export_snapshot()` (InMemory) or Neo4j `export_snapshot()` via Cypher; for large production graphs callers should prefer `statistics()`/`neighborhood()` aggregations.

## Health

`GET /api/health` reports `graph.neo4j: connected|disconnected|disabled` based on live `verify_connectivity()` at startup and on each health call if currently disconnected.

## Testing

No separate Neo4j persistence tests in `tests/test_persistence.py` (graph is tested via `tests/test_analysis.py` and `tests/test_api.py` `GET /api/analysis`, `GET /api/network`). To test against a live Neo4j:

```bash
docker compose up -d neo4j
pytest tests/test_api.py::test_analysis_global -v
pytest tests/test_api.py::test_get_neighborhood -v
```

If Neo4j is unavailable, `app/config.py` falls back to `InMemoryGraphRepository` so tests still pass.
