# Architecture Decisions — SIH 26189

Status: living document. Each decision records context, decision, and
consequences. Decisions marked PROVISIONAL require explicit approval to
change.

## ADR-001: Backend runtime — Express bootstrap now, FastAPI migration proposed

**Status:** PROVISIONAL — do **not** delete or rewrite the existing backend
until migration is explicitly approved.

### Context

The repository currently contains a minimal Node.js/TypeScript Express
service (`backend/src/index.ts`) that only serves stub endpoints
(`/api/health`, `/api/entities`, `/api/network`) and no business logic.

Meanwhile, the core workload of this system lives in Python:

- Entity/relationship extraction (`ai/entity_extraction.py`,
  `ai/relationship_extraction.py`)
- Canonical schemas (`ai/schemas.py`)
- Synthetic data generation (`ai/synthetic_data_generator.py`)
- Graph construction / NetworkX analytics (`graph/graph_construction.py`)
- Evidence provenance hashing (`blockchain/evidence_chain.py`)

Future milestones add graph algorithms, temporal pattern detection, and ML
(NER) — all Python-native (NetworkX, scikit-learn, spaCy/transformers).
A Node.js API layer over these would require a permanent cross-language
RPC/bridge, duplicating validation logic that already exists in
`ai/schemas.py`.

### Decision

1. The current Express service is classified as a **bootstrap layer only**:
   it proves the deployment pipeline (Docker, ports, health checks) and is
   kept runnable. No new domain logic will be added to it.
2. The target architecture is **Python FastAPI** for the primary API:
   - Same process boundary as the AI/graph/data modules (no RPC hop)
   - Native async I/O for Neo4j/Postgres drivers
   - Pydantic models can mirror `EntitySchema`/`RelationshipSchema`
   - Auto-generated OpenAPI docs for the frontend team
3. Migration path when approved: port the three stub routes first, run
   Express and FastAPI in parallel behind docker-compose, cut over the
   frontend, then retire `backend/`.

### Consequences

- Short term: two small services in docker-compose; acceptable overhead.
- Long term: one language (Python) for data, AI, graph, and API.
- Risk: none material — the Express service contains no irreplaceable code.

## ADR-002: Canonical model is contract-first

**Status:** Accepted.

`ai/schemas.py` is the single source of truth (12 entity types,
11 relationship types, mandatory provenance). The PostgreSQL schema
(`db/001_initial_schema.sql`), the Neo4j mapping (`docs/graph-model.md`),
and the synthetic generator all derive from it. Changes to the model must
update `schemas.py` first, then the SQL migration, docs, and tests together.

## ADR-003: Stable TEXT IDs instead of UUIDs

**Status:** Accepted.

IDs follow `{prefix}-{5 digits}` (e.g. `person-00042`, `rel-00117`). They are
human-readable, deterministic, and enable idempotent upserts (same ID ⇒ same
entity), which UUID v4 cannot provide. PostgreSQL CHECK constraints enforce
format/prefix per table; Neo4j nodes key on `entity_id`.

## ADR-004: Blockchain = provenance chain only

**Status:** Accepted for this milestone.

Evidence integrity uses hash-chained records (`blockchain/evidence_chain.py`
computes `chain_hash`). No consensus, mining, tokens, or smart contracts —
a permissioned append-only log satisfies evidence-chain-of-custody needs
without a public network.

## ADR-005: Safety-first labeling

**Status:** Accepted, non-negotiable.

No schema field, synthetic record, or analytic output assigns guilt,
criminality, or risk verdicts to individuals. The system surfaces entities,
relationships, patterns, anomalies, and evidence connections; interpretation
belongs to human investigators.

## ADR-006: AI pipeline is stage-oriented and composable

**Status:** Accepted (Milestone 3).

The investigation pipeline is a sequence of independently callable stages:
Preprocessing → Entity Extraction → Entity Resolution → Relationship
Extraction → Validation → Persistence → Graph Synchronization. Each stage
is a public method on `InvestigationPipeline` with a typed contract. This
enables:
- Unit testing each stage in isolation
- Swapping extractors (PatternEntityExtractor ↔ SpacyEntityExtractor)
- Replacing persistence (InMemory → PostgreSQL) without touching logic
- Replacing graph sync (InMemoryGraphRepository ↔ Neo4jGraphRepository)

No hidden global state; all dependencies injected at construction.

## ADR-007: Entity extraction abstraction

**Status:** Accepted.

`EntityExtractor` (ABC) with implementations:
- `PatternEntityExtractor` — deterministic regex/structural rules, always available.
- `SpacyEntityExtractor` — spaCy NER (optional, lazily imported; falls back to patterns).

Future transformer-based extractors implement the same ABC. All return
`ExtractedEntity` with explicit `extraction_method` ("pattern:..." or
"spacy:..."). Confidence is never fabricated: pattern rules use declared
priors; spaCy returns `None` (no calibrated score).

## ADR-008: Deterministic entity resolution only

**Status:** Accepted for Milestone 3.

`DeterministicEntityResolver` applies explicit rules:
- Exact normalized phone/account/vehicle → auto-linked (confidence=1.0).
- Normalized person/org name → candidates only, `needs_review` (confidence=0.60).
- No probabilistic scoring, no automatic merges.

Ambiguous matches are returned as candidates requiring human review.
Probabilistic identity models are explicitly deferred.

## ADR-009: Relationship extraction requires explicit cues

**Status:** Accepted.

`RuleBasedRelationshipExtractor` only creates relationships when:
- A textual cue regex matches between two mentions (e.g., "works for",
  "called", "transferred to", "traveled to", "owns", "associated with"),
  OR
- A structured record (transaction, event) provides authoritative evidence.

Co-occurrence alone is **insufficient**. Every relationship carries a fixed
rule prior from `RULE_PRIORS` (not fabricated per result).

## ADR-010: Graph repository abstraction

**Status:** Accepted.

Application code depends on `GraphRepository` (ABC) with methods:
- `upsert_entity`, `upsert_relationship`
- `get_entity`, `get_relationships`
- `neighborhood`, `shortest_path`, `statistics`

Implementations:
- `InMemoryGraphRepository` — tests, local dev, no Docker.
- `Neo4jGraphRepository` — lazy `neo4j` driver import; production.

Cypher uses canonical model: nodes keyed on `entity_id`, labels = entity
type, relationship types = canonical set.

## ADR-011: Analysis uses neutral terminology with explainability

**Status:** Accepted, non-negotiable.

All analytical indicators use neutral vocabulary:
- `high_network_centrality`, `bridge_candidate`
- `connection_density`, `community_membership`
- `relationship_intensity`, `pattern_indicator`, `anomaly_indicator`

**Forbidden**: "criminal probability", "guilt probability", "likely criminal",
"risk score", "criminal score".

Every indicator includes:
- `reason`: human-readable explanation grounded in graph structure
- `evidence`: list of relationship_ids supporting the finding

No explanation generated without supporting data.

## ADR-012: FastAPI as the target API (Provisional → Accepted)

**Status:** Accepted (Milestone 3 delivery).

The `backend-python/` service exposes all Milestone 3 endpoints via FastAPI
with Pydantic contracts mirroring the canonical schemas. The Express
bootstrap service (`backend/`) remains in compose but receives no new logic.

## ADR-013: PostgreSQL is the canonical store; Neo4j is the analytical projection (Milestone 4)

**Status:** Accepted.

**Context:** Milestone 3 used `InMemoryPersistence` for the pipeline and an
in-memory graph fallback. The schema `db/001_initial_schema.sql` already
existed as the source of truth, but no real persistence was wired.

**Decision:**
- **PostgreSQL** = canonical structured persistence. Owns the 12 entity
  tables + `relationships` table, TEXT IDs, CHECK constraints, provenance
  columns. All writes are parameterized (`%s`), idempotent (`ON CONFLICT DO
  UPDATE`), and transaction-safe (`with persistence.transaction():`). Implemented
  as `ai.persistence.PostgresPersistence` behind `ai.persistence.base.PersistenceBase`.
- **Neo4j** = relationship/network analytical projection. Owns the graph
  (`entity_id` as key, labels = entity_type, relationship types = canonical
  set). Used for `neighborhood`, `shortestPath`, `statistics`, and
  `export_snapshot()` via Cypher. Never the primary source of truth.
- **In-memory** = testing/development fallback. `ai.persistence.memory.InMemoryPersistence`
  and `app.graph.memory.InMemoryGraphRepository` remain and are used when
  `DATABASE_URL`/`NEO4J_ENABLED` are unavailable, so unit tests never require
  Docker.

**Consequences:**
- Pipeline is now `InvestigationPipeline(persistence=...)` — injection, not
  global state. Tests default to in-memory; production / `docker compose`
  injects PostgreSQL (`ai.load_synthetic_data` imports synthetic JSON
  idempotently).
- Synthetic import is explicit (`python -m ai.load_synthetic_data [--reset]`)
  and reports `inserted/updated/errors`; re-running is idempotent.
- Health endpoint distinguishes `database.postgresql` vs `graph.neo4j`.
- No passwords are logged; no string-concatenated SQL.

## ADR-014: Health endpoint reports real connectivity (Milestone 4)

**Status:** Accepted.

`GET /api/health` now returns:
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
`neo4j_connected` is kept for backwards compatibility. Values are
`connected` only after a live `SELECT 1` / `verify_connectivity()` check;
otherwise `disconnected` or `disabled`. No fake “connected”.

## ADR-015: Graph export is via Cypher, not full in-memory load (Milestone 4)

**Status:** Accepted.

`Neo4jGraphRepository.export_snapshot()` now fetches all nodes/relationships
via Cypher (`MATCH (n)`, `MATCH ()-[r]->()`) for the synthetic scale
(~150 nodes, 446 rels). For larger graphs, callers should use
`statistics()`/`neighborhood()` aggregations instead of full export. This
replaces the previous `NotImplementedError` with a bounded implementation.

## ADR-016: Graph Intelligence is deterministic, NetworkX-based (Milestone 5)

**Status:** Accepted.

**Context:** The system displayed relationships but lacked analytical signals. The
synthetic dataset (seed 42) already contains communities, bridge nodes, repeated
contacts, transaction chains, and temporal bursts that should be detected.

**Decision:**
- Use **NetworkX** for in-memory/graph-projection analysis (deterministic,
  no additional infrastructure). Metrics are real calculations, not invented:
  - `degree_centrality` (degree/(n-1))
  - `betweenness_centrality` (normalized, `betweenness_centrality`)
  - `closeness_centrality` (`closeness_centrality`)
  - `pagerank` (`pagerank` damping 0.85)
  All returned normalized 0..1, rounded 6 decimals, sorted.
- Communities: **`greedy_modularity_communities`** (NetworkX, deterministic on
  sorted nodes) → `{community_id, members, size, internal_edges, density}`
  (IDs `community-000` sorted by min member). No “gangs” terminology.
- Bridges: articulation points (Tarjan) + high betweenness (>0.05) + community
  boundary (≥2 neighboring communities). Returns `{entity_id, metric, score,
  explanation, evidence}`. Metric is `articulation_point` / `community_boundary`
  / `betweenness_centrality`.
- All outputs are explainable (`reason`/`explanation` + `evidence` relationship_ids)
  and deterministic (sorted). No ML/LLM; future ML is a later milestone.

## ADR-017: Relationship strength is explainable, not a criminal score (Milestone 5)

**Status:** Accepted.

`interaction_strength` per relationship is a weighted, normalized (0..1) combination
of: type weight (`TRANSFERRED_TO` 1.5, `CALLED` 1.2, etc.), confidence, pair
frequency (`(freq-1)*0.15` capped 1.0), timestamp bonus (+0.1 if present).
Formula: `min(1, (w*0.3+conf*0.4+freq*0.2+bonus)/1.5)`. Returns
`{relationship_id, interaction_strength, factors, explanation}` sorted desc.
Never called “criminal association score”.

## ADR-018: Temporal and transaction-chain analysis are statistical, not ML (Milestone 5)

**Status:** Accepted.

- **Temporal bursts:** bucket relationships by 24h windows from `timestamp`,
  per-entity `mean + 2*std` threshold; flag windows `cnt > threshold && cnt>=3`.
  Returns `{indicator_type, time_window, observed_count, baseline{mean,std,threshold},
  explanation, evidence}`. Types: `temporal_burst` / `communication_burst` / `transaction_burst`.
- **Transaction chains:** directed `TRANSFERRED_TO` graph (`DiGraph`), DFS up to 4 hops
  (min 2), deduplicated by evidence set, up to 20 chains → `{chain_id,
  source_account, intermediates, destination, hop_count, evidence, explanation}`.
  Chain existence alone is not “suspicious”; rule is documented.

## ADR-019: Indicator model severity is analytical, not criminality (Milestone 5)

**Status:** Accepted.

Structured indicator: `{indicator_id, indicator_type, severity, entity_ids,
relationship_ids, score, explanation, evidence, created_at}`. Severity
`LOW`/`MEDIUM`/`HIGH` = signal strength (e.g., `HIGH` = `score>=0.75` = density
substantially above baseline), not “HIGH RISK CRIMINAL”. Every indicator
contains `what was observed, how it was calculated, which entities/relationships
contributed, why it was surfaced`. Forbidden outputs remain blocked
(`criminal probability`, `guilt probability`, etc. – tested).

## ADR-020: Investigation subgraph, paths, findings, evidence, snapshot (Milestone 8A)

**Status:** Accepted.

**Decision:**
- Subgraph: `case → root → N-hop (0..6) → filtered → bounded (200 nodes/400 rels) → deterministic sorted → truncated flag`. Intersection with case network if `case_id` provided. Validates `depth`/`max_nodes` 400 else 400, `entity_types`/`relationship_types` filters, preserves provenance.
- Paths: `shortestPath` via `GraphRepository`, enriched to `{nodes (full entity), edges (full relationship provenance), hop_count, relationship_sequence, provenance}`. Validates `max_depth` 1..6, entity existence 404, never fabricates.
- Findings: deterministic candidate findings from M5 intelligence (bridge/temporal/chain/strength), `finding_id = hash(sorted(entity_ids)|type|case|salt)`, `severity` LOW/MEDIUM/HIGH analytical, `explanation` covers what/why/which, `provenance` per finding, max 20 sorted by `finding_id`.
- Evidence: `collect_evidence` aggregates entity/relationship/path/indicator into deduplicated `evidence_id` items, max 50, `evidence_type` ∈ entity/relationship/path/indicator.
- Snapshot: `snapshot_id = hash(case|root|depth|max_nodes)`, combines subgraph + up to 3 paths + findings + evidence, `generated_at` fixed `2024-01-01T00:00:00Z` for determinism, ephemeral (no DB persistence in this milestone per spec).

**Consequences:** Frontend gets stable, typed `POST/GET /api/investigations/*` contracts for workspace; no guilt scoring.

## ADR-021: Explainability model — lineage and reproducibility (Milestone 9A)

**Status:** Accepted.

**Decision:**
- Typed `ExplanationOut` with `explanation_id`, `analysis_type`, `summary`, `methodology`, `observations`, `contributing_entities/relationships`, `supporting_evidence`, `parameters`, `thresholds`, `limitations`, `provenance`, `generated_at`, `lineage{analysis_type, algorithm, parameters, inputs, observations, output_summary, dataset_id, deterministic, timestamp}`, `reproducibility{analysis_type, entity_id, dataset_id, result_id, deterministic}`.
- Covers 8 families: centrality (degree/betweenness/closeness/PageRank via NetworkX), communities (greedy_modularity), bridges (Tarjan + betweenness), temporal (24h mean+2*std), transaction chains (DiGraph DFS), relationship strength (weighted), indicators, findings, entity (observed vs analytical).
- All explanations reuse M5/M8 outputs (adapter, not recompute for presentation unless via same deterministic algorithm). `dataset_id` = hash of `counts`/`_generation_config`. `generated_at` fixed for determinism.
- `explain_entity` distinguishes `observed_data{entity, relationships}` vs `analytical_interpretation{centrality, community, is_bridge, indicators}`.

## ADR-023: AI provider architecture — analytical-assistance layer (Milestone 12A)

**Status:** Accepted.

**Context:** Milestones 3–9 established deterministic extraction (pattern/rules), statistical graph intelligence (NetworkX), investigation engine (M8), explainability + lineage + provenance (M9), and evidence hash-chain (M11). Text extraction remained regex-based and interpretation was algorithmic without an AI-assisted summarization layer. The product requires a genuine AI-assisted layer that interprets structured results and assists extraction while preserving canonical truth and safety.

**Decision:**
- **Provider abstraction:** `ai/providers/base.py` defines `AIProvider` ABC with `extract_entities`, `extract_relationships`, `analyze_patterns`, `status`. Business logic depends on `AIAnalyzer` facade (`ai/ai_analyzer.py`), not hard-coded API clients. Configuration via env only (`AI_PROVIDER`, `AI_LOCAL_MODEL`, `AI_LOCAL_TIMEOUT_MS`); no API keys in source. Provider-independent, adapter-based.
- **Providers:** `DeterministicAIProvider` (always available, reuses PatternEntityExtractor + RuleBasedRelationshipExtractor + NetworkX; deterministic hashes, needs_review thresholds 0.60 entity / 0.70 relationship) and `LocalAIProvider` (requires `AI_PROVIDER=local` + `AI_LOCAL_MODEL=mock-local` or project-relative path; if missing => `ProviderUnavailable` 503 truthfully; file access scoped to project root; timeout 1..30s). Unknown provider => unavailable (no silent fallback).
- **Extraction flow:** AI extracts mentions with canonical 12 types, value, start/end, confidence (declared priors), extraction_method (`deterministic:pattern:...` / `local:...`), provenance (provider/version/model/start/end), `needs_review` (< threshold), metadata (normalized_value, entity_id if known). IDs are **never invented** — canonical IDs come from `EntityIndex`/persistence. Relationships use canonical 11 types, source/target indices, confidence, extraction_method, provenance, `needs_review`, evidence_span; unknown types never become valid; low confidence => `needs_review` not persisted as fact; validation (`ai/schemas.py` CHECK + `RelationshipSchema.validate`) remains authoritative.
- **Interpretation layer:** AI receives structured graph snapshot (entities, relationships, centrality, communities, bridges, temporal, chains, indicators — the M5/M8 outputs) and produces grounded summary: `observations[]` (what was measured) + `analytical_interpretation[]` (what it means, neutral) + methodology/limitations. Graph engine remains source of truth; AI does not invent nodes/edges.
- **Structured output:** `AIAnalysisOut` (`backend-python/app/schemas.py`) with `analysis_id` (deterministic `ai-{hash}`), `analysis_type`, `summary`, `observations`, `analytical_interpretation`, `supporting_entity/relationship/evidence_ids`, `confidence` (0..1, analytical not guilt — validated `ge=0 le=1` + forbidden terminology check), `methodology`, `limitations` (investigator-assistance disclaimer), `provenance` (provider/version/model/timestamp/case_id), `lineage` (algorithm, params, inputs, dataset_id, deterministic), `reproducibility` (provider/version/input_hash/result_id/deterministic).
- **Explainability integration:** Every AI result includes provider, provider_version, model when available, dataset_id (`hash(entity_ids)`), deterministic flag, input_hash/output_hash, timestamp, provenance, lineage, reproducibility. Uses M9 patterns (FIXED_GENERATED_AT for determinism) without creating parallel system.
- **Audit:** Every AI request records `event_type=ai_analysis_requested` via existing bounded audit (`app/services/audit.py` deque 1000, sanitized params — drops password/secret/token/connection_string). Query via `GET /api/audit/events?analysis_type=...` as before.
- **Determinism:** Same input + provider config + graph dataset + params => same result. Deterministic provider is fully reproducible (hashed IDs, sorted outputs). Local generative would be marked `deterministic=False` with input_hash/output_hash recorded.
- **Security:** Bounded inputs (100k text, 500 entities, 500k snapshot), prompt injection treated as data (sanitize_text, no execution, logs use `_sanitize_params`), no arbitrary model URLs (file must be project-relative), no secrets in logs/responses, no unsafe file/code execution.
- **Failure behavior:** Typed errors: 400 empty/unsupported, 404 invalid case/entity, 422 oversized/invalid canonical type, 503 unavailable, 504 timeout, 502 malformed, 500 forbidden terminology. Never silent fallback from failed real AI to fabricated intelligence; deterministic mode is explicit.

**Consequences:** Frontend gets typed `/api/ai/*` endpoints; deterministic mode works without external AI; local model can be added later without changing business logic; safety and reproducibility are first-class; no guilt scoring.

## ADR-024: M13 — Evaluated Local AI + Grounding + Briefs

**Status:** Accepted.

**Context:** M12 delivered provider abstraction (deterministic + local mock), 8.5k evaluation not yet present, grounding validation was implicit, briefs were not formalized, local model was mock-local only. M13 requires measurable, grounded, locally executable intelligence.

**Decision:**
- **Evaluation dataset:** `tests/fixtures/ai/scenarios.json` v13.0.0 — 8 synthetic scenarios (simple, multi-hop, communities+bridge, temporal, transaction chain, ambiguous/noisy, negative/empty, injection). Each with `text`, `expected_entities` (value+canonical_type), `expected_relationships` (source/target/type), `graph_snapshot` (entities/relationships with metrics), `expected_observations`. Ground truth describes observable properties, never guilt.
- **Metrics:** `ai/evaluation/metrics.py` `entity_metrics` / `relationship_metrics` via exact value+type match (precision/recall/F1, tp/fp/fn). `ai/evaluation/runner.py` measures both providers, latency (avg/median/max, timeout count), groundedness via `ai/grounding.py`, confidence calibration (correct vs incorrect avg), reproducibility. Results persisted to `tests/evaluation/results/latest.json`. Command: `python -m ai.evaluation` or `pytest tests/evaluation`.
- **Grounding validator:** `ai/grounding.py` — validates entity/relationship/evidence IDs exist in snapshot, case membership via RELATED_TO_CASE/MENTIONED_IN, numerical facts (counts), temporal facts (timestamps). Returns `SUPPORTED`/`NEEDS_REVIEW` with unsupported lists; integrated into `DeterministicAIProvider.analyze_patterns` as `grounding_status`/`grounding_details` added to `AIAnalysisOut`. Unsupported not silently deleted but flagged.
- **Briefs:** New `analysis_type` values `investigation_brief` / `entity_brief` / `network_brief` accepted in `ai/providers/deterministic.py` and `backend-python/app/ai_router.py`; generation reuses same grounded logic with brief-specific human-review note. `network_brief` is case-scoped when `case_id` supplied (backend filters snapshot to `related_ids`, see audit §4).
- **Local model:** `ai/providers/local.py` enhanced with lazy `threading.Lock` model init, `_load_model()` attempting `transformers` local-only load if path exists, `_with_timeout()` via `ThreadPoolExecutor` enforcing `AI_LOCAL_TIMEOUT_MS` 1..30s → `ProviderTimeout` 504, URL rejection (`://` → unavailable), path traversal blocked (`resolved.startswith(project_root)`). For `mock-local` sentinel, remains deterministic delegation; for real path, `deterministic=False` with input/output hashes. No auto-download; `LOCAL_MODEL_BLOCKER` reported when `transformers` missing.
- **Frontend:** `AIWorkspace` dropdown now 11 types (adds 3 briefs), `grounding_status` badge (SUPPORTED green / NEEDS_REVIEW amber) in result panel, briefs use same observed/interpretation/provenance/lineage UI.
- **Safety:** Prompt injection treated as data (`sanitize_text`, not executed; `tests/test_ai.py:prompt_injection` + scenario 08); forbidden terminology check via `_FORBIDDEN_SCORING` (scoring phrases only, allows disclaimers); input bounds 100k/500/200/500k enforced; output validated via Pydantic; secrets never logged.

**Consequences:** Deterministic baseline remains reproducible reference; local generative can be evaluated side-by-side; every AI result is traceable to graph IDs; evaluation provides measurable precision/recall/F1 and groundedness.

## ADR-022: Audit trail — analytical, bounded, no secrets (Milestone 9A)

**Status:** Accepted.

**Decision:**
- In-memory bounded store (`deque maxlen 1000`, `FIXED_TIMESTAMP` for determinism) with `AuditEventOut{ audit_id (deterministic hash of event_type|analysis_type|object_id|sorted params), event_type, timestamp, case_id, entity_id, root_entity_id, analysis_type, object_id, parameters (sanitized), provenance, status}`.
- Events: `analysis_requested/completed`, `investigation_created`, `finding_generated`, `evidence_generated`, `snapshot_generated`, `explainability_requested`. Recorded inline in relevant endpoints (analysis, investigation, explainability) with sanitized `parameters` (drops `password`/`secret`/`token`/`connection_string`, small lists only, `<type:len>` for large).
- Query: `GET /api/audit/events?case_id&analysis_type&event_type&entity_id&root_entity_id&start_time&end_time&limit 1..100&offset` → deterministic `timestamp, audit_id` sorted, `count/total`, never unbounded dump. `POST /api/audit/events/clear` for tests (no auth per spec, analytical audit not identity).
- No credential/env/header logging; uses references not payload copies.

