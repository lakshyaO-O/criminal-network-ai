# Persistence — SIH 26189 (Milestone 4)

PostgreSQL is the **canonical structured store**; Neo4j is the **analytical graph projection**; In-memory is the **test fallback**.

```
Raw Input → Pipeline → PostgreSQL (canonical) → Neo4j (projection)
                         ↑                           ↑
                     health: SELECT 1           health: verify_connectivity()
```

## PostgreSQL (canonical)

**Schema source of truth:** `db/001_initial_schema.sql` (12 entity tables + `relationships`, TEXT IDs `{prefix}-00001`, CHECK constraints, no UUIDs).

**Implementation:** `ai/persistence/postgres.py` `PostgresPersistence` behind `ai/persistence/base.py`.

- Parameterized SQL only (`%s`, never string-concatenated user input).
- Idempotent upserts: `INSERT ... ON CONFLICT (pk) DO UPDATE ... RETURNING (xmax=0)` → `inserted` vs `updated`.
- Provenance preserved: `relationship_id, source_id, source_type, target_id, target_type, timestamp, confidence, extraction_method, created_at, metadata`.
- Transaction-safe: `with persistence.transaction():` (psycopg `autocommit=False` → `commit()`/`rollback()`).
- Driver: tries `psycopg` (v3) then `psycopg2`; install via `pip install "psycopg[binary]" psycopg2-binary`.
- Config: `DATABASE_URL` (or `APP_DATABASE_URL`/`POSTGRES_*` / `.env` via `python-dotenv` not required for tests). Default `postgresql://investigator:secure_password@localhost:5432/criminal_network?connect_timeout=2` (matches `docker-compose.yml`).
- No credential logging.

**Health:** `persistence.health_check()` does `SELECT 1` and checks `to_regclass('public.relationships')`.

## In-Memory (fallback / tests)

`ai/persistence/memory.py` `InMemoryPersistence` — dicts `entities`/`relationships`, `transaction()` snapshots for rollback, `health_check()=True`. Used when `DATABASE_URL` unreachable so `53` existing tests never require Docker.

Pipeline injection:

```python
from ai.persistence.memory import InMemoryPersistence
from ai.persistence.postgres import PostgresPersistence

# Production / local with DB
persistence = PostgresPersistence() if PostgresPersistence().health_check() else InMemoryPersistence()

pipeline = InvestigationPipeline(
    extractor=PatternEntityExtractor(...),
    resolver=DeterministicEntityResolver(...),
    relationship_extractor=RuleBasedRelationshipExtractor(),
    persistence=persistence,
    graph_repository=graph_repo,
)
```

Default test behavior remains in-memory; no DB required.

## Synthetic Import (idempotent)

**Command:** `python -m ai.load_synthetic_data [--data-dir data/synthetic] [--dsn URL] [--reset] [--json]`

- Loads `data/synthetic/*.json` (persons … evidence + relationships).
- Validates each relationship via `ai.schemas.RelationshipSchema`.
- Upserts entities then relationships (entities first for FKs).
- Reports:

```
Entities inserted: 142
Entities updated: 0
Relationships inserted: 446
Relationships updated: 0
Errors: 0
```

Re-running is idempotent: second run → `0 inserted, N updated, 0 errors` (because `ON CONFLICT DO UPDATE`).

**Reset:** `--reset` explicitly drops/recreates via `init_schema()`; otherwise schema is created only if missing (`health_check` fails). Never silently destroys existing DB.

## API Integration

`backend-python/app/config.py` `create_persistence()` tries PostgreSQL then falls back to in-memory. `backend-python/app/api.py` `startup()` sets `_persistence` and `_persistence_health["postgresql"]`. Entity/case lookups prefer PostgreSQL (`_persistence.get_entity`) then fallback to synthetic JSON dataset. `GET /api/health` reports `database.postgresql: connected|disconnected|in_memory`.

## Testing

`tests/test_persistence.py` covers in-memory contract (always runnable) and PostgreSQL when available:

- entity insert / upsert
- relationship insert / upsert / provenance
- retrieval (entity, relationships, case, evidence)
- idempotent import
- transaction rollback

PostgreSQL tests are **skipped** (not faked) when `health_check` fails:

```
pytest tests/test_persistence.py -v
# 6 passed, 5 skipped (if no DB)
# with DB: 11 passed
```

Run synthetic-data tests:

```
python -m unittest discover -s tests -v  # 21 OK
```

## Security

- Never log `DATABASE_URL` / passwords.
- Use parameterized queries (`%s`).
- Validate API inputs via Pydantic (`backend-python/app/schemas.py`).
