# FastAPI Endpoints — SIH 26189 (Milestones 3–9A)

Base URL: `http://localhost:8000/api` (port 8001 for backend-python Docker)

Persistence: PostgreSQL canonical store (`ai/persistence/postgres.py`) + Neo4j graph projection (`app/graph/neo4j_repo.py`) + in-memory fallback for tests (`GET /api/health` reports real connectivity).

All endpoints return structured JSON. Neutral terminology only — no
criminality/guilt scores.

---

## Health

### `GET /api/health` (Milestone 4: now distinguishes PostgreSQL and Neo4j)

```json
{
  "status": "ok",
  "service": "criminal-network-analysis",
  "version": "1.0.0",
  "neo4j_connected": true,
  "database": {"postgresql": "connected"},
  "graph": {"neo4j": "connected"}
}
```

`neo4j_connected` is legacy and kept for backwards compat. `database.postgresql` is `connected` only after `SELECT 1` succeeds (`psycopg` with `connect_timeout=2`); `graph.neo4j` only after `verify_connectivity()` succeeds. Values are `connected`/`disconnected`/`disabled`/`in_memory` — never faked. See `docs/persistence.md` and `docs/neo4j.md`.

---

## Extraction

### `POST /extraction/entities`

Extract entity mentions from raw text.

**Request**
```json
{
  "text": "Rhea Verma works for Bluepeak Traders Pvt Ltd. Called +91-901234567.",
  "source_id": "doc-001",
  "use_spacy": false
}
```

**Response**
```json
{
  "source_id": "doc-001",
  "entity_count": 4,
  "entities": [
    {
      "text": "Rhea Verma",
      "entity_type": "Person",
      "start_offset": 0,
      "end_offset": 10,
      "normalized_value": "Rhea Verma",
      "entity_id": "person-00001",
      "confidence": 0.4,
      "extraction_method": "pattern:person_titlecase",
      "source_id": "doc-001",
      "metadata": {}
    },
    {
      "text": "Bluepeak Traders Pvt Ltd",
      "entity_type": "Organization",
      "start_offset": 19,
      "end_offset": 43,
      "normalized_value": "Bluepeak Traders Pvt Ltd",
      "entity_id": "org-00001",
      "confidence": 0.8,
      "extraction_method": "pattern:org_suffix",
      "source_id": "doc-001",
      "metadata": {}
    },
    {
      "text": "+91-901234567",
      "entity_type": "PhoneNumber",
      "start_offset": 56,
      "end_offset": 69,
      "normalized_value": "+91-901234567",
      "entity_id": "phone-00001",
      "confidence": 0.95,
      "extraction_method": "pattern:phone_fictional",
      "source_id": "doc-001",
      "metadata": {}
    }
  ]
}
```

### `POST /extraction/relationships`

Extract relationships from text and/or structured records.

**Request**
```json
{
  "text": "Rhea Verma works for Bluepeak Traders Pvt Ltd. Rhea Verma traveled to Sector 12 Market.",
  "source_id": "doc-002",
  "entities": [],  // optional pre-extracted
  "structured_records": [
    {
      "record_type": "transaction",
      "transaction_id": "transaction-00001",
      "from_account_id": "account-00001",
      "to_account_id": "account-00002",
      "amount": "50000",
      "currency": "INR",
      "timestamp": "2024-06-15T10:00:00Z"
    }
  ]
}
```

**Response**
```json
{
  "source_id": "doc-002",
  "relationship_count": 3,
  "relationships": [
    {
      "relationship_id": "rel-00001",
      "source": {"entity_id": "person-00001", "entity_type": "Person", "text": "Rhea Verma"},
      "target": {"entity_id": "org-00001", "entity_type": "Organization", "text": "Bluepeak Traders Pvt Ltd"},
      "relationship_type": "WORKS_FOR",
      "timestamp": null,
      "confidence": 0.8,
      "extraction_method": "rule:works_for_cue",
      "source_id": "doc-002",
      "metadata": {"cue_window_verified": true}
    },
    {
      "relationship_id": "rel-00002",
      "source": {"entity_id": "person-00001", "entity_type": "Person", "text": "Rhea Verma"},
      "target": {"entity_id": "location-00001", "entity_type": "Location", "text": "Sector 12 Market"},
      "relationship_type": "TRAVELED_TO",
      "timestamp": null,
      "confidence": 0.75,
      "extraction_method": "rule:traveled_to_cue",
      "source_id": "doc-002",
      "metadata": {"cue_window_verified": true}
    },
    {
      "relationship_id": "transaction-00001",
      "source": {"entity_id": "account-00001", "entity_type": "FinancialAccount", "text": "50000"},
      "target": {"entity_id": "account-00002", "entity_type": "FinancialAccount", "text": ""},
      "relationship_type": "TRANSFERRED_TO",
      "timestamp": "2024-06-15T10:00:00Z",
      "confidence": 1.0,
      "extraction_method": "rule:transferred_to_structured",
      "source_id": "transaction-00001",
      "metadata": {"currency": "INR"}
    }
  ]
}
```

---

## Investigation Pipeline

### `POST /investigations/analyze`

Run the full pipeline: preprocess → extract → resolve → relate → validate → persist → sync graph.

**Request**
```json
{
  "text": "Rhea Verma works for Bluepeak Traders Pvt Ltd. Called +91-901234567.",
  "source_id": "doc-003",
  "use_spacy": false,
  "persist": true,
  "sync_graph": true
}
```

**Response**
```json
{
  "source_id": "doc-003",
  "preprocessed_text": "Rhea Verma works for Bluepeak Traders Pvt Ltd. Called +91-901234567.",
  "entities": [...],
  "resolutions": {
    "0:10:Rhea Verma": [
      {
        "candidate_entity_id": "person-00001",
        "match_method": "normalized_person_name",
        "confidence": 0.6,
        "supporting_fields": ["full_name"],
        "status": "needs_review"
      }
    ]
  },
  "relationships": [...],
  "validation_errors": [],
  "persisted": {"entities": 3, "relationships": 2},
  "graph_sync": {"nodes": 3, "relationships": 2}
}
```

---

## Entity Lookups (PostgreSQL canonical, fallback to synthetic JSON)

### `GET /entities/{entity_id}`

Returns canonical entity record from PostgreSQL (`ai.persistence.PostgresPersistence` via `GET /api/entities/{id}` → `get_entity` → `SELECT * FROM {table} WHERE pk = %s`) if DB is `connected`; otherwise falls back to synthetic dataset (`data/synthetic/*.json`). Same for `GET /api/cases/{case_id}` and relationships via graph projection.

```json
{
  "entity_id": "person-00001",
  "entity_type": "Person",
  "full_name": "Rhea Verma",
  "date_of_birth": "1985-03-12",
  "nationality": "IN (fictional)",
  "metadata": {"note": "synthetic person"},
  "created_at": "2024-01-15T10:30:00Z"
}
```

### `GET /entities/{entity_id}/relationships`

All relationships where this entity is source or target.

```json
{
  "entity_id": "person-00001",
  "relationships": [
    {
      "relationship_id": "rel-00001",
      "source": {"entity_id": "person-00001", "entity_type": "Person", "text": "Rhea Verma"},
      "target": {"entity_id": "org-00001", "entity_type": "Organization", "text": "Bluepeak Traders"},
      "relationship_type": "WORKS_FOR",
      "confidence": 0.8,
      "extraction_method": "rule:works_for_cue",
      "source_id": "doc-001",
      "metadata": {}
    }
  ]
}
```

### `GET /entities/{entity_id}/neighborhood?depth=1`

Breadth-first neighborhood up to `depth` (1..6).

```json
{
  "start_entity_id": "person-00001",
  "depth": 1,
  "nodes": [
    {"entity_id": "person-00001", "depth": 0},
    {"entity_id": "org-00001", "depth": 1},
    {"entity_id": "phone-00001", "depth": 1}
  ],
  "edges": [
    {"from": "person-00001", "to": "org-00001", "relationship_type": "WORKS_FOR"},
    {"from": "person-00001", "to": "phone-00001", "relationship_type": "CALLED"}
  ]
}
```

---

## Cases

### `GET /cases/{case_id}`

```json
{
  "case_id": "case-00001",
  "case_number": "SYN-CASE-2024-001",
  "title": "Inquiry 001 (synthetic)",
  "description": "Synthetic investigation record...",
  "case_type": "financial_irregularity",
  "status": "open",
  "assigned_to": "person-00005",
  "opened_at": "2024-02-10T09:00:00Z",
  "metadata": {"classification": "SYNTHETIC_DEMO"}
}
```

---

## Network

### `GET /network/{case_id}`

Subgraph of all entities/relationships linked to a case via
`RELATED_TO_CASE` or `MENTIONED_IN`.

```json
{
  "case_id": "case-00001",
  "entities": [...],
  "relationships": [...],
  "statistics": {
    "node_count": 12,
    "relationship_count": 28,
    "type_counts": {"Person": 8, "Organization": 2, ...},
    "relationship_type_counts": {"KNOWS": 10, "WORKS_FOR": 5, ...},
    "avg_degree": 4.67
  }
}
```

---

## Analysis

### `GET /analysis`

Global descriptive analysis of the entire synthetic graph.

```json
{
  "counts": {"entities": 150, "relationships": 446, "connected_components": 3, "communities_detected": 5},
  "entity_type_counts": {"Person": 30, "Organization": 6, ...},
  "relationship_type_counts": {"KNOWS": 120, "WORKS_FOR": 45, ...},
  "degree_statistics": {"min": 1, "max": 18, "average": 5.9, "connection_density": 0.04},
  "highly_connected_entities": [{"entity_id": "person-00012", "degree": 18}, ...],
  "components_preview": [...],
  "communities": [{"community_index": 0, "size": 25, "member_entity_ids": [...]}],
  "temporal_activity": [{"month": "2024-03", "relationship_count": 42}, ...],
  "indicators": [
    {
      "entity_id": "person-00012",
      "indicator": "high_network_centrality",
      "reason": "Entity participates in 18 observed relationships across 3 entity types",
      "evidence": ["rel-00045", "rel-00067", ...]
    },
    {
      "entity_id": "person-00003",
      "indicator": "bridge_candidate",
      "reason": "Removing this entity would disconnect previously linked parts of the network (5 direct connections; network currently has 3 connected components)",
      "evidence": ["rel-00012", "rel-00034", ...]
    }
  ],
  "terminology_notice": "Descriptive indicators only. This system does not assess guilt or criminality; all findings support human review."
}
```

### `GET /analysis/{case_id}`

Same analysis restricted to the case subgraph.

---

## Graph Intelligence — Milestone 5 (deterministic, explainable)

All endpoints below are under `GET /api/analysis/*` and use `backend-python/app/services/network_analysis.py` (NetworkX `degree`/`betweenness`/`closeness`/`pagerank`, `greedy_modularity_communities`, `articulation_points`). Scores are real calculations, not invented. Terminology is neutral (`interaction_strength`, `bridge_candidate`, `network community`).

### `GET /api/analysis` (enriched in Milestone 5)

Now returns additional keys (backward compatible with Milestone 3):

```json
{
  "counts": {...},
  "centrality": {
    "degree": {"person-00001": 0.12, ...},
    "betweenness": {"person-00001": 0.08, ...},
    "closeness": {"person-00001": 0.45, ...},
    "pagerank": {"person-00001": 0.02, ...}
  },
  "centrality_explanations": {
    "degree": "Number of direct connections relative to graph size...",
    "betweenness": "Frequency entity lies on shortest paths...",
    "closeness": "Inverse average distance...",
    "pagerank": "Link-analysis score (damping 0.85)..."
  },
  "communities_detailed": [
    {"community_id": "community-000", "members": ["person-00001", ...], "size": 5, "internal_edges": 10, "density": 0.5}
  ],
  "bridges_detailed": [
    {"entity_id": "person-00001", "entity_type": "Person", "metric": "articulation_point", "score": 0.12, "explanation": "Articulation point: removing ...", "evidence": ["rel-00001", ...]}
  ],
  "temporal_indicators": [
    {"indicator_type": "temporal_burst", "time_window": "2024-03-10T00:00:00+00:00/2024-03-11T00:00:00+00:00", "entity_ids": ["person-00001"], "observed_count": 5, "baseline": {"mean": 1.2, "std": 0.5, "threshold": 2.2}, "explanation": "Observed 5 interactions ...", "evidence": ["rel-00001"]}
  ],
  "transaction_chains": [
    {"chain_id": "chain-account-00001-account-00003-0000", "source_account": "account-00001", "intermediate_accounts": ["account-00002"], "destination_account": "account-00003", "hop_count": 2, "evidence": ["rel-00123", "rel-00124"], "explanation": "Directed transaction chain of 2 hops ..."}
  ],
  "relationship_strength": [
    {"relationship_id": "rel-00001", "interaction_strength": 0.85, "factors": {"type_weight": 1.5, "confidence": 0.9, "pair_frequency": 3}, "explanation": "interaction_strength 0.85 from type 'TRANSFERRED_TO'..."}
  ],
  "indicators_enhanced": [
    {"indicator_id": "ind-centrality-person-00001", "indicator_type": "high_betweenness_centrality", "severity": "HIGH", "entity_ids": ["person-00001"], "relationship_ids": ["rel-00001"], "score": 0.82, "explanation": "Entity person-00001 has betweenness ... does not imply criminality...", "evidence": ["rel-00001"], "created_at": "2024-01-01T00:00:00Z"}
  ]
}
```

### `GET /api/analysis/centrality`

```json
{
  "centrality": {"degree": {...}, "betweenness": {...}, "closeness": {...}, "pagerank": {...}},
  "explanations": {"degree": "...", "betweenness": "...", "closeness": "...", "pagerank": "..."}
}
```

### `GET /api/analysis/communities`

```json
{
  "communities": [{"community_id": "community-000", "members": ["person-00001", ...], "size": 5, "internal_edges": 8, "density": 0.4}],
  "count": 5
}
```

### `GET /api/analysis/bridges`

```json
{
  "bridges": [{"entity_id": "person-00001", "entity_type": "Person", "metric": "articulation_point", "score": 0.12, "explanation": "...", "evidence": ["rel-00001"]}],
  "count": 2
}
```

### `GET /api/analysis/temporal`

Detects 24h bursts vs baseline (`mean + 2*std`). Returns `temporal_indicators` with `time_window`, `observed_count`, `baseline`, `explanation`.

### `GET /api/analysis/transaction-chains`

Directed `TRANSFERRED_TO` chains `A → B → C` (2–4 hops), deterministic via sorted DFS, deduplicated.

### `GET /api/analysis/relationship-strength`

Explainable `interaction_strength` per relationship (type weight + confidence + pair frequency + timestamp bonus), sorted desc.

### `GET /api/analysis/indicators`

Structured indicators:

```json
{
  "indicators": [
    {"indicator_id": "ind-bridge-person-00001", "indicator_type": "bridge_articulation_point", "severity": "MEDIUM", "entity_ids": ["person-00001"], "relationship_ids": ["rel-00001"], "score": 0.6, "explanation": "Articulation point ... not a guilt assessment.", "evidence": ["rel-00001"], "created_at": "2024-01-01T00:00:00Z"}
  ],
  "count": 12
}
```

`severity` = `LOW`/`MEDIUM`/`HIGH` = analytical signal strength, **not** criminality. All indicators contain `explanation` + `evidence`.

### `GET /api/analysis/path?source_id=person-00001&target_id=person-00012&max_depth=6`

```json
{"found": true, "length": 2, "entities": ["person-00001", "person-00005", "person-00012"], "relationships": ["KNOWS", "KNOWS"]}
```

Validates entities exist (404 else) and `max_depth` 1..6 (400 else). Never fabricates paths.

### `GET /api/analysis/entities/{entity_id}` and `GET /api/analysis/entities/{entity_id}/centrality`

Per-entity centrality + neighborhood + indicators. Uses same metrics as global, scoped.

All new endpoints are deterministic, cached where practical, and fall back to in-memory when Neo4j is `disconnected` (never report Neo4j-derived data unless Neo4j actually supplied it). No guilt/criminality scoring.

---

## Investigation Engine — Milestone 8A (deterministic, provenance-aware)

Base URL remains `http://localhost:8000/api`. All investigation endpoints are under `/api/investigations/*` and are **investigator-oriented**: they turn graph-analysis results into structured evidence and candidate findings. No guilt scoring.

### Limits (explicit, deterministic)

- `depth` / `max_depth`: 0..6 (400 if violated)
- `max_nodes`: 1..500 (default 200)
- `max_relationships`: 1..1000 (default 400)
- `max_paths`: 20, `max_findings`: 20, `truncated` flag when limits hit
- Ordering: entities sorted by `entity_id`, relationships by `relationship_id`, findings by `finding_id`

### `GET /api/investigations/subgraph` and `POST /api/investigations/subgraph`

Investigator-focused subgraph: `case → root → N-hop → filtered`, bounded, deterministic.

**GET query params:**

- `root_entity_id` (required, e.g., `person-00001`)
- `depth` (0..6, default 1)
- `case_id` (optional, e.g., `case-00001`; if provided, subgraph is intersected with case network `RELATED_TO_CASE`/`MENTIONED_IN`)
- `entity_types` (comma-separated canonical 12, e.g., `Person,Organization`)
- `relationship_types` (comma-separated canonical 11, e.g., `KNOWS,CALLED`)
- `max_nodes` (1..500, default 200)
- `max_relationships` (1..1000, default 400)

**POST body (`InvestigationSubgraphRequest`):**

```json
{
  "case_id": "case-00001",
  "root_entity_id": "person-00001",
  "depth": 2,
  "entity_types": ["Person", "Organization"],
  "relationship_types": ["KNOWS"],
  "max_nodes": 200,
  "max_relationships": 400
}
```

**Response (`InvestigationSubgraphResponse`):**

```json
{
  "case_id": "case-00001",
  "root_entity": {"entity_id": "person-00001", "entity_type": "Person", "full_name": "Hema Verma", ...},
  "depth": 2,
  "entities": [{"entity_id": "person-00001", ...}, {"entity_id": "person-00002", ...}],
  "relationships": [{"relationship_id": "rel-00001", "source_id": "person-00001", "source_type": "Person", "target_id": "person-00002", "target_type": "Person", "relationship_type": "KNOWS", "confidence": 0.9, "extraction_method": "manual_entry", "provenance": {...}}],
  "statistics": {"node_count": 12, "edge_count": 18, "entity_type_counts": {"Person": 8}, "relationship_type_counts": {"KNOWS": 10}, "depth": 2, "truncated": false, "max_nodes": 200},
  "truncated": false,
  "provenance": [{"source": "graph_repo", "analysis_type": "neighborhood", "timestamp": "2024-01-01T00:00:00Z", "root_entity_id": "person-00001", "depth": 2}]
}
```

**Errors:** 400 for `depth`/`max_nodes` out of bounds, 404 for missing `root_entity_id` or `case_id`. No full-graph dump when depth is small.

**Example:**

```bash
curl "http://localhost:8000/api/investigations/subgraph?root_entity_id=person-00001&depth=2&case_id=case-00001"
```

### `GET /api/investigations/paths` and `POST /api/investigations/paths`

Multi-hop investigator-friendly paths (enriched nodes/edges, `relationship_sequence`, provenance).

**GET query:**

- `source_id` (required)
- `target_id` (required)
- `max_depth` (1..6, default 6)
- `case_id` (optional)
- `relationship_types` (optional filter)

**POST body (`InvestigationPathRequest`):**

```json
{"source_id": "person-00001", "target_id": "account-00003", "max_depth": 6, "case_id": "case-00001"}
```

**Response (`InvestigationPathResponse`):**

```json
{
  "found": true,
  "hop_count": 3,
  "nodes": [
    {"entity_id": "person-00001", "entity_type": "Person", "full_name": "Hema Verma"},
    {"entity_id": "phone-00001", "entity_type": "PhoneNumber", "number": "+91-91-9897858"},
    {"entity_id": "person-00012", "entity_type": "Person", "full_name": "Aarav Sharma"},
    {"entity_id": "account-00003", "entity_type": "FinancialAccount", "account_number": "FICA..."}
  ],
  "edges": [
    {"relationship_id": "rel-00010", "source_id": "person-00001", "source_type": "Person", "target_id": "phone-00001", "target_type": "PhoneNumber", "relationship_type": "OWNS", "confidence": 0.97, "extraction_method": "cdr_record"},
    {"relationship_id": "rel-00111", "source_id": "phone-00001", "source_type": "PhoneNumber", "target_id": "person-00012", "target_type": "Person", "relationship_type": "CALLED", "confidence": 0.95, "extraction_method": "cdr_record"}
  ],
  "relationship_sequence": ["OWNS", "CALLED", "OWNS"],
  "provenance": [{"source": "graph_repo", "analysis_type": "shortest_path", "timestamp": "2024-01-01T00:00:00Z", "max_depth": 6}]
}
```

If `found: false`, `nodes`/`edges` are empty, `hop_count: null`. Never invents `relationship_sequence`.

### `GET /api/investigations/findings`

Candidate findings aggregated from intelligence (bridges, centrality, temporal bursts, transaction chains, strong relationships). Each finding is deterministic, explainable, provenance-aware.

**Query:**

- `case_id` (optional)
- `root_entity_id` (optional)
- `depth` (0..6, default 2, used when `root_entity_id` provided)

**Response (`InvestigationFindingsResponse`):**

```json
{
  "case_id": "case-00001",
  "root_entity_id": "person-00001",
  "count": 4,
  "findings": [
    {
      "finding_id": "finding-a1b2c3d4e5f6",
      "finding_type": "bridge_entity",
      "title": "Bridge entity connecting network regions: person-00009",
      "severity": "MEDIUM",
      "explanation": "Observed network pattern: entity person-00009 (Person) Articulation point: removing ... This was selected because high betweenness indicates it links otherwise separated groups. Supporting evidence includes 5 relationships. This is a candidate finding for investigator review, not a guilt assessment.",
      "entity_ids": ["person-00009"],
      "relationship_ids": ["rel-00013", "rel-00016", "rel-00018"],
      "supporting_paths": [],
      "indicators": [{"indicator_id": "ind-bridge-person-00009", "indicator_type": "bridge_articulation_point", "severity": "MEDIUM", "score": 0.6, "explanation": "...", "evidence": ["rel-00013"]}],
      "temporal_evidence": [],
      "transaction_evidence": [],
      "centrality_context": {"betweenness": 0.101, "degree": 0.2},
      "community_context": null,
      "evidence": [],
      "provenance": [{"source": "network_analysis", "analysis_type": "articulation_point", "timestamp": "2024-01-01T00:00:00Z"}],
      "created_at": "2024-01-01T00:00:00Z"
    },
    {
      "finding_id": "finding-b2c3d4e5f6g7",
      "finding_type": "temporal_burst",
      "title": "Repeated interaction burst: temporal_burst",
      "severity": "MEDIUM",
      "explanation": "Observed pattern: Observed 4 interactions for 'person-00001' in 24h window ... compared to baseline mean 1.12 ...",
      "entity_ids": ["person-00001"],
      "relationship_ids": ["rel-00040", "rel-00376"],
      "temporal_evidence": [{"indicator_type": "temporal_burst", "time_window": "2025-02-04T01:52:44+00:00/2025-02-05T01:52:44+00:00", "observed_count": 4, "baseline": {"mean": 1.12, "std": 0.51}, "explanation": "...", "evidence": ["rel-00040"]}],
      "provenance": [{"source": "network_analysis", "analysis_type": "temporal", "timestamp": "2024-01-01T00:00:00Z"}],
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "provenance": [{"source": "investigation_engine", "analysis_type": "findings", "timestamp": "2024-01-01T00:00:00Z"}]
}
```

`finding_type` values: `bridge_entity`, `temporal_burst`, `transaction_chain`, `strong_relationship` (others may be added deterministically, sorted by `finding_id`, max 20). `severity` is analytical signal (`LOW`/`MEDIUM`/`HIGH`), never `crime_probability`. All findings contain `explanation` (what/why/which) and `evidence`/`provenance`.

**Errors:** 400 for `depth` out of bounds, 404 for missing `case_id`/`root_entity_id`.

### `GET /api/investigations/evidence`

Aggregated evidence items for a (case, root) context.

**Query:** same as findings (`case_id`, `root_entity_id`, `depth`)

**Response:** `List[InvestigationEvidenceOut]`

```json
[
  {
    "evidence_id": "ev-entity-person-00001",
    "evidence_type": "entity",
    "description": "Entity person-00001 (Person) present in investigation subgraph",
    "entity_ids": ["person-00001"],
    "relationship_ids": [],
    "indicator_ids": [],
    "provenance": [{"source": "graph_repo", "analysis_type": "subgraph", "timestamp": "2024-01-01T00:00:00Z"}],
    "created_at": "2024-01-01T00:00:00Z"
  },
  {
    "evidence_id": "ev-rel-rel-00001",
    "evidence_type": "relationship",
    "description": "Relationship rel-00001 KNOWS person-00001→person-00002",
    "entity_ids": ["person-00001", "person-00002"],
    "relationship_ids": ["rel-00001"],
    "indicator_ids": [],
    "provenance": [{"source": "graph_repo", "analysis_type": "relationship", "timestamp": "2024-01-01T00:00:00Z", "extraction_method": "manual_entry"}],
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

`evidence_type` ∈ `entity`/`relationship`/`path`/`indicator`. Deterministic, deduplicated, up to 50.

### `POST /api/investigations/snapshot` and `GET /api/investigations/snapshot`

Deterministic investigation workspace snapshot (ephemeral, not persisted to DB in this milestone; `snapshot_id` is hash of `case_id|root|depth|max_nodes`).

**POST body (`InvestigationSnapshotRequest`):**

```json
{
  "case_id": "case-00001",
  "root_entity_id": "person-00001",
  "depth": 2,
  "entity_types": ["Person"],
  "relationship_types": ["KNOWS"],
  "include_findings": true,
  "include_paths": true,
  "max_nodes": 200
}
```

**GET query:** same fields as query params (`root_entity_id` required, `depth` 0..6, `max_nodes` 1..500)

**Response (`InvestigationSnapshotResponse`):**

```json
{
  "snapshot_id": "snapshot-a1b2c3d4e5f6",
  "case_id": "case-00001",
  "root_entity": {"entity_id": "person-00001", "entity_type": "Person", "full_name": "Hema Verma"},
  "depth": 2,
  "entities": [{"entity_id": "person-00001", ...}, ...],
  "relationships": [{"relationship_id": "rel-00001", ...}, ...],
  "paths": [{"found": true, "hop_count": 2, "nodes": [...], "edges": [...], "relationship_sequence": ["KNOWS", "KNOWS"]}],
  "findings": [{"finding_id": "finding-...", "finding_type": "bridge_entity", "severity": "MEDIUM", "explanation": "...", "entity_ids": [...], "provenance": [...]}],
  "evidence": [{"evidence_id": "ev-entity-person-00001", "evidence_type": "entity", "description": "...", "provenance": [...]}],
  "statistics": {"node_count": 18, "edge_count": 24, "entity_type_counts": {"Person": 10}, "relationship_type_counts": {"KNOWS": 8}, "depth": 2, "truncated": false},
  "generated_at": "2024-01-01T00:00:00Z",
  "provenance": [{"source": "graph_repo", "analysis_type": "neighborhood", "timestamp": "2024-01-01T00:00:00Z"}, {"source": "investigation_engine", "analysis_type": "snapshot", "timestamp": "2024-01-01T00:00:00Z"}]
}
```

**Errors:** 400 for `depth`/`max_nodes` bounds or missing `root_entity_id`, 404 for missing `case_id`/`root_entity_id`. `generated_at` is deterministic `2024-01-01T00:00:00Z` for reproducibility.

All investigation endpoints preserve canonical IDs/types, provenance (`extraction_method`, `confidence`, `timestamp`, `source`), and use neutral terminology (`candidate finding`, `observed pattern`, `supporting evidence`). Performance is bounded: depth≤6, nodes≤500, findings≤20, paths≤5 per snapshot, deduplication.

---

## Explainability, Lineage & Audit — Milestone 9A (deterministic, provenance-aware)

All analytical results are explainable, traceable, reproducible, and auditable. No `crime_probability`/`guilt` scoring.

### Explanation Model (`ExplanationOut`)

```json
{
  "explanation_id": "expl-bridge-person-00001-a1b2c3",
  "analysis_type": "bridge",
  "summary": "Bridge person-00001 via articulation_point score 0.1200",
  "methodology": "Articulation point (Tarjan DFS) ... betweenness from NetworkX ...",
  "observations": ["Metric articulation_point score 0.1200", "Evidence 5 relationships"],
  "contributing_entities": ["person-00001"],
  "contributing_relationships": ["rel-00001", "rel-00002"],
  "supporting_evidence": ["rel-00001"],
  "parameters": {"betweenness_threshold": 0.05},
  "thresholds": {"betweenness": 0.05},
  "limitations": "Bridge indicates structural position, not guilt. ...",
  "provenance": [{"source": "network_analysis", "analysis_type": "articulation_point", "timestamp": "2024-01-01T00:00:00Z"}],
  "generated_at": "2024-01-01T00:00:00Z",
  "lineage": {
    "analysis_type": "bridge",
    "algorithm": "tarjan+betweenness",
    "parameters": {"threshold": 0.05},
    "inputs": {"entity_id": "person-00001"},
    "observations": ["score 0.12"],
    "output_summary": "Bridge person-00001",
    "dataset_id": "dataset-a1b2c3",
    "deterministic": true,
    "timestamp": "2024-01-01T00:00:00Z"
  },
  "reproducibility": {"analysis_type": "bridge", "entity_id": "person-00001", "dataset_id": "dataset-a1b2", "result_id": "expl-bridge-person-00001-a1b2c3", "deterministic": true}
}
```

Lineage answers WHAT/WHY/WHICH data/WHICH algorithm/PARAMETERS/WHEN/WHERE/REPRODUCIBILITY/LIMITATIONS. Reuses M5/M8 outputs (no recompute for presentation unless needed; if recomputed, via same deterministic algorithm).

### `GET /api/explainability/findings/{finding_id}`

Explain a specific finding (M8 deterministic `finding_id`).

- **Params:** `finding_id` (path, e.g., `finding-a1b2c3d4e5f6`)
- **Response:** `ExplanationOut` (above) + `finding` (original `InvestigationFindingOut` under `finding` key for frontend)
- **Errors:** 404 `Finding '...' not found`, 500 analysis failure
- **Example:** `GET /api/explainability/findings/finding-a1b2c3d4e5f6` → 200 with `analysis_type: "finding"`, `methodology: "Finding generated deterministically from bridge/temporal/chain/strength..."`, `provenance` includes `network_analysis` + `investigation_engine`
- **Audit:** `explainability_requested` event recorded

### `GET /api/explainability/entities/{entity_id}`

Entity-level intelligence explanation (observed data vs analytical interpretation).

- **Params:** `entity_id` (path)
- **Response:** `ExplanationOut` with `observed_data{entity, relationships[:10]}` and `analytical_interpretation{centrality, community, is_bridge, indicators}` separated.
- **Example:** `GET /api/explainability/entities/person-00001` → summary `Entity person-00001 (Person) has 12 relationships; bridge=false, community=community-000`, methodology `Observed: entity record + relationships; Analytical: centrality/community/bridge/indicators`, limitations `Distinguishes observed from interpretation, not guilt`
- **Errors:** 404

### `GET /api/explainability/centrality` and `GET /api/explainability/centrality/{entity_id}`

- **Query:** `entity_id` (required for `/centrality` query, path for `/{entity_id}`)
- **Response:** `ExplanationOut` for centrality (`analysis_type: "centrality"`, `methodology` covers degree/betweenness/closeness/PageRank NetworkX, `observations` degree 0.12 etc., `parameters` `alpha:0.85`, `thresholds` `high_betweenness:0.05`, `lineage` dataset_id)
- **Example:** `GET /api/explainability/centrality?entity_id=person-00001` → `summary: "Centrality for person-00001: degree 0.1200..."`

### `GET /api/explainability/communities` and `GET /api/explainability/communities/{entity_id}`

- **Params:** `entity_id?`/`case_id?` (query for communities)
- **Response:** community assignment explanation (`analysis_type: "community"`, methodology `greedy_modularity`, observations `Graph has 5 communities...`)

### `GET /api/explainability/bridges/{entity_id}`

- **Response:** bridge explanation (`analysis_type: "bridge"`, metric `articulation_point` etc., score, `thresholds` 0.05, limitations)

### `GET /api/explainability/temporal` and `GET /api/explainability/transaction-chains` and `GET /api/explainability/indicators/{indicator_id}` and `GET /api/explainability/relationship-strength/{relationship_id}`

Each returns `ExplanationOut` with analysis-specific methodology (`24h windows mean+2*std`, `DiGraph DFS 2–4 hops`, `weighted interaction_strength`, etc.), `observations`, `thresholds`, `lineage`.

### `GET /api/audit/events`

Bounded, deterministic audit retrieval. Never dumps secrets.

- **Query:** `case_id?`, `analysis_type?`, `event_type?` (e.g., `analysis_requested`, `finding_generated`, `explainability_requested`), `entity_id?`, `root_entity_id?`, `start_time?`, `end_time?` (ISO), `limit` 1..100 (default 50), `offset` ≥0
- **Response:** `AuditQueryResponse` (`events: AuditEventOut[]`, `count`, `total`, `limit`, `offset`, sorted by `timestamp` asc then `audit_id`)
- `AuditEventOut`: `audit_id` (deterministic `audit-{hash}`), `event_type`, `timestamp` fixed `2024-01-01T00:00:00Z` for determinism, `case_id?`, `entity_id?`, `root_entity_id?`, `analysis_type?`, `object_id?`, `parameters` (sanitized, no passwords/secrets, small lists only), `provenance`, `status`
- **Errors:** 400 for `limit`/`offset` out of bounds
- **Example:** `GET /api/audit/events?case_id=case-00001&event_type=finding_generated&limit=20` → 200 with 4 events
- **Security:** `_SENSITIVE_KEYS` (`password`, `secret`, `token`, `connection_string`, `database_url`, `dsn`) never logged; `parameters` sanitized to `<type:len>` for large payloads; no env vars, no headers

### `POST /api/audit/events/clear`

- Clears in-memory audit store (for tests; no auth as per milestone, analytical audit not identity). Returns `{"status":"cleared","count":0}`.

All explainability/audit endpoints are bounded (`limit` ≤100, findings ≤20), deterministic (`sorted`, `hash` IDs), and use `FIXED_GENERATED_AT` (`2024-01-01T00:00:00Z`) for reproducibility. Audit events are automatically recorded on `analysis`/`investigation`/`explainability` calls (e.g., `investigation_created`, `finding_generated`, `explainability_requested`, `analysis_requested`).

---

## AI-Assisted Analysis — Milestone 12A (provider-independent, analytical only)

All AI endpoints are under `/api/ai/*`. They provide **investigator-assistance** analytical interpretation, never guilt/criminality scoring. Every AI output distinguishes **observed data** from **analytical interpretation**, includes **provenance**, **lineage**, **reproducibility**, and **limitations**. Confidence means analytical extraction/interpretation confidence, never p(guilt).

### Provider architecture

- `AIProvider` ABC (`ai/providers/base.py`) with `extract_entities`, `extract_relationships`, `analyze_patterns`, `status`.
- `DeterministicAIProvider` (`ai/providers/deterministic.py`) — always available, reuses PatternEntityExtractor + RuleBasedRelationshipExtractor + NetworkX; deterministic hashed IDs, fixed methodology.
- `LocalAIProvider` (`ai/providers/local.py`) — requires `AI_PROVIDER=local` + `AI_LOCAL_MODEL=mock-local` (or valid project-relative path); if not configured returns 503 `AI provider unavailable` (never fabricates). Checks file within project root, timeout bounded, marks reproducibility appropriately.
- `AIAnalyzer` facade (`ai/ai_analyzer.py`) selects provider via env, bounds inputs (max 100k text, 500 entities, 200 structured records), sanitizes logs, never logs secrets.

### `GET /api/ai/status`

Provider health. No secrets returned.

```json
{
  "provider": "deterministic",
  "provider_version": "12A-1.0.0",
  "available": true,
  "model": "deterministic-rules",
  "deterministic": true,
  "description": "Deterministic AI provider ...",
  "input_max_len": 100000
}
```

Audit: `ai_analysis_requested` with `analysis_type=status`.

### `POST /api/ai/extract/entities`

AI-assisted entity extraction over investigation text, canonical 12 types, grounded extraction.

**Request**
```json
{
  "text": "Rhea Verma works for Bluepeak Traders Pvt Ltd. +91-90-1234567",
  "source_id": "doc-001",
  "provider": "deterministic"
}
```
Validation: `text` 1..100000 (400 if empty/oversized, 422 if too long), `source_id` max 200. `provider` optional override.

**Response**
```json
{
  "source_id": "doc-001",
  "provider": "deterministic",
  "provider_version": "12A-1.0.0",
  "model": "deterministic-rules",
  "entities": [
    {
      "canonical_type": "Person",
      "value": "Rhea Verma",
      "start": 0,
      "end": 10,
      "confidence": 0.4,
      "extraction_method": "deterministic:pattern:person_titlecase",
      "provenance": {"provider": "deterministic", "extraction_method": "pattern:person_titlecase", "start": 0},
      "needs_review": true,
      "metadata": {"normalized_value": "Rhea Verma", "entity_id": "person-99901"}
    }
  ],
  "entity_count": 3,
  "provenance": [{"source": "ai_provider", "provider": "deterministic"}],
  "lineage": {"analysis_type": "entity_extraction", "algorithm": "deterministic:pattern+rules", "deterministic": true, "timestamp": "2024-01-01T00:00:00Z"},
  "reproducibility": {"provider": "deterministic", "input_hash": "c593b22e0137", "deterministic": true}
}
```
IDs are **not invented** by AI — resolved via `EntityIndex` if known, else `entity_id` stays None until canonical resolution. `needs_review` true when `confidence <0.60`. Errors: 400 empty, 422 oversized (>100k), 422 invalid canonical_type, 503 unavailable, 504 timeout, 502 malformed.

### `POST /api/ai/extract/relationships`

AI-assisted relationship extraction over entities + text/structured records. Preserves canonical 11 relationship types.

**Request**
```json
{
  "text": "Rhea Verma works for Bluepeak Traders Pvt Ltd.",
  "entities": [{"canonical_type": "Person", "value": "Rhea Verma", "start": 0, "end": 10, "confidence": 0.4, "extraction_method": "deterministic:pattern:person_titlecase", "provenance": {}, "needs_review": true, "metadata": {}}],
  "structured_records": [{"record_type": "transaction", "from_account_id": "account-00001", "to_account_id": "account-00002", "amount": "50000"}],
  "provider": "deterministic"
}
```
Bounded: `entities` max 500, `structured_records` max 200 (400 otherwise). Unknown relationship types never become valid (422 if violated). Low confidence (`<0.70`) => `needs_review`.

**Response**
```json
{
  "relationships": [{"source_entity_index": 0, "target_entity_index": 1, "relationship_type": "WORKS_FOR", "confidence": 0.8, "extraction_method": "deterministic:rule:works_for_cue", "needs_review": false}],
  "relationship_count": 1,
  "provenance": [{"source": "ai_provider"}],
  "lineage": {...},
  "reproducibility": {...}
}
```

### `POST /api/ai/analyze`

AI-assisted interpretation over structured graph snapshot (grounded).

**Request**
```json
{
  "analysis_type": "network_summary",
  "case_id": "case-00001",
  "root_entity_id": "person-00001",
  "graph_snapshot": {"entities": {"person-00001": ["Person", {}]}, "relationships": [{"relationship_id": "rel-00001"}]},
  "provider": "deterministic"
}
```
`analysis_type` ∈ `network_summary|centrality|community|bridge|temporal|transaction_chain|indicator|finding|investigation_brief|entity_brief|network_brief` (400 otherwise). `case_id`/`root_entity_id` validated 404 if unknown. `text` optional (1..100k). `graph_snapshot` optional — if omitted derived from current `export_snapshot()` filtered to `case_id` when supplied (case-scoped, prevents cross-case leakage; deterministic NetworkX metrics). Snapshot oversized (>500k stringified) => 400.

**Response (`AIAnalyzeResponse`)**
```json
{
  "provider": "deterministic",
  "provider_version": "12A-1.0.0",
  "analysis": {
    "analysis_id": "ai-f6b3c7e811d3",
    "analysis_type": "network_summary",
    "summary": "AI-assisted interpretation for network_summary: Observed graph snapshot: 302 entities, 446 relationships",
    "observations": ["Observed graph snapshot: 302 entities, 446 relationships", "Observed 10 bridge candidates"],
    "analytical_interpretation": ["Analytical interpretation: centrality indicates structural position not guilt"],
    "supporting_entity_ids": ["account-00001"],
    "supporting_relationship_ids": ["rel-00001"],
    "supporting_evidence_ids": ["rel-00001"],
    "confidence": 0.85,
    "methodology": "Deterministic provider: PatternEntityExtractor + RuleBasedRelationshipExtractor + NetworkX; grounded summary",
    "limitations": "Analytical interpretation only; does not determine guilt, criminality, or wrongdoing; requires investigator review",
    "provenance": [{"source": "ai_provider", "provider": "deterministic", "analysis_type": "network_summary"}],
    "lineage": {"analysis_type": "network_summary", "algorithm": "deterministic:networkx+rules", "dataset_id": "dataset-3272155dc684", "deterministic": true},
    "reproducibility": {"provider": "deterministic", "input_hash": "b9c073284f41", "deterministic": true}
  },
  "provenance": [...],
  "lineage": {...},
  "reproducibility": {...}
}
```
`confidence` is analytical interpretation confidence (0..1, validated), **not** guilt probability. Methodology/limitations are explicit, neutral. `graph_snapshot` is source of truth — AI never invents graph facts. Errors: 400 unsupported analysis_type/empty text/oversized, 404 invalid case/entity, 503 unavailable, 504 timeout, 502 malformed, 500 forbidden terminology violation (never).

### Audit for AI

Every AI request records `event_type=ai_analysis_requested` via bounded audit (`GET /api/audit/events` filters as before). Parameters sanitized (no password/secret/token/connection_string), provenance includes provider/version/model/timestamp, lineage includes dataset_id/deterministic/input_hash. Use `GET /api/audit/events?analysis_type=network_summary&limit=20` to query.

### Failure behavior

- `provider unavailable` → 503 with `AI provider unavailable` (deterministic never unavailable; local unavailable when not configured).
- `timeout` → 504 (real `ThreadPoolExecutor` timeout `AI_LOCAL_TIMEOUT_MS` 1..30s; simulated via `TIMEOUT_SIM` marker for tests).
- `malformed` → 502 (simulated via `MALFORMED_SIM`).
- `empty input` → 400.
- `oversized` (>100k text, >500 entities, >500k snapshot) → 422/400.
- Unknown provider → 503, never silent fallback to fabricated intelligence. Deterministic fallback is explicit provider/mode, not silent.

### Evaluation & Grounding (M13)

- **Dataset:** `tests/fixtures/ai/scenarios.json` v13.0.0 — 8 synthetic scenarios (see `docs/architecture.md ADR-024`).
- **Metrics:** `python -m ai.evaluation` or `pytest tests/evaluation -q` — entity/relationship precision/recall/F1, groundedness (via `ai/grounding.py`), latency (avg/median/max/timeout), confidence calibration, reproducibility.
- **Grounding:** Every `AIAnalysisOut` now includes `grounding_status` (`SUPPORTED`/`NEEDS_REVIEW`) and `grounding_details` (entity/relationship/evidence/case/numerical/temporal checks). Unsupported claims are flagged, not silently deleted; frontend shows grounding badge.
- **Briefs:** `investigation_brief` / `entity_brief` / `network_brief` — same grounded logic, case-scoped when `case_id` supplied (backend filters snapshot to `RELATED_TO_CASE` subgraph).
- **Local model:** Configure `AI_PROVIDER=local` + `AI_LOCAL_MODEL=path` (project-relative, no URL). Real model load attempted via `transformers` `local_files_only=True` (no auto-download); if missing → `LOCAL_MODEL_BLOCKER` and `503`. See `ai/providers/local.py`.

---

## OpenAPI

`GET /openapi.json` — full OpenAPI 3.1 spec (auto-generated by FastAPI).

Swagger UI: `GET /docs`  
ReDoc: `GET /redoc`