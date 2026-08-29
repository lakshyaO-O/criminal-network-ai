# Canonical Data Model — SIH 26189

> **Safety principle.** This is an investigator-assistance system. It
> identifies entities, relationships, patterns, anomalies, and evidence
> connections from authorized data. It does **not** determine guilt, assign
> criminal labels, or assert that any individual is a criminal.

## 1. Overview

The canonical model is the single source of truth shared by:

| Layer | Artifact |
|---|---|
| Python contract | `ai/schemas.py` (`EntitySchema`, `RelationshipSchema`) |
| PostgreSQL | `db/001_initial_schema.sql` |
| Graph (Neo4j) | `docs/graph-model.md` |
| Demo data | `ai/synthetic_data_generator.py` → `data/synthetic/` |

- 12 entity types
- 11 relationship types
- Mandatory provenance on every relationship

## 2. Stable IDs

Every entity has a stable, human-readable, deterministic ID:

```
{prefix}-{5-digit counter}     e.g. person-00042, rel-00117
```

| Entity | Prefix | Example | PK column |
|---|---|---|---|
| Person | `person-` | person-00001 | `person_id TEXT` |
| Organization | `org-` | org-00003 | `org_id TEXT` |
| PhoneNumber | `phone-` | phone-00012 | `phone_id TEXT` |
| Vehicle | `vehicle-` | vehicle-00007 | `vehicle_id TEXT` |
| Location | `location-` | location-00002 | `location_id TEXT` |
| FinancialAccount | `account-` | account-00009 | `account_id TEXT` |
| Transaction | `transaction-` | transaction-00045 | `transaction_id TEXT` |
| Communication | `comm-` | comm-00120 | `comm_id TEXT` |
| Case | `case-` | case-00004 | `case_id TEXT` |
| FIR | `fir-` | fir-00004 | `fir_id TEXT` |
| Event | `event-` | event-00025 | `event_id TEXT` |
| Evidence | `evidence-` | evidence-00008 | `evidence_id TEXT` |
| Relationship | `rel-` | rel-00446 | `relationship_id TEXT` |

Rules:

1. IDs are **TEXT**, not UUIDs — synthetic and ingested data must load
   idempotently (same ID ⇒ same entity, upsert semantics).
2. Prefix always matches entity type (`ai.schemas.validate_entity_id`).
3. Counters are per-dataset; a dataset's `_generation_config.json` records
   its seed so IDs are reproducible.
4. Self-loop relationships (`source_id == target_id`, same type) are forbidden.

## 3. Entity Types

All entities carry common fields: `entity_id`, `<type>_id` (same value),
`entity_type`, type-specific columns, `metadata JSONB`, `created_at`.

### Person
`full_name`, `date_of_birth`, `nationality`. No guilt/criminality fields by
design — status language is neutral ("mentioned in case X").

### Organization
`name`, `registration_number`, `jurisdiction`.

### PhoneNumber
`number` (E.164-style), `phone_type` (mobile/landline/fax), `carrier`.

### Vehicle
`registration_number`, `make`, `model`, `year`, `color`, `vin`.

### Location
`latitude`, `longitude`, `description`, `area_name`,
`metadata.accuracy_meters`.

### FinancialAccount
`account_number` (masked in UIs), `account_type`, `institution`,
`jurisdiction`, `currency`.

### Transaction (event-like)
`amount DECIMAL(15,2)`, `transaction_type`, `currency`, `from_account_id →
FinancialAccount`, `to_account_id → FinancialAccount`, `timestamp`,
optional demo flag `is_flagged_demo`.

### Communication (event-like)
`medium` (call/sms/email/chat), `direction`, `from_entity_id`,
`to_entity_id` (polymorphic Person/Organization), optional
`from_phone_id`/`to_phone_id`, `duration_seconds`, `timestamp`.

### Case
`case_number UNIQUE`, `title`, `description`, `case_type`, `status`
(open / under_investigation / closed), `assigned_to → Person`,
`opened_at`.

### FIR (report)
`fir_number UNIQUE`, `case_id → Case`, `fir_type` (FIR/complaint/
intel_report), `filed_at`, `filed_by → Person`, `jurisdiction`.

### Event (observed activity)
`name`, `description`, `event_type` (meeting/sighting/handoff/travel),
`timestamp`, `location_id → Location`.

### Evidence
`case_id → Case`, `description` (metadata only — never raw content),
`evidence_type`, `source`, `collected_at`, `collected_by → Person`,
`chain_hash` (populated by `blockchain/evidence_chain.py`),
`status` (logged/in_custody/under_review).

## 4. Relationship Types

Directed unless noted. Every relationship row stores full provenance.

| Type | From → To | Direction | Notes |
|---|---|---|---|
| KNOWS | Person → Person | bidirectional | stored once; symmetric |
| CALLED | Person → Person (via phones) | directed | backed by Communication records |
| TRANSFERRED_TO | Account → Account | directed | backed by Transaction records |
| LOCATED_AT | Entity → Location | directed | current/observed position |
| TRAVELED_TO | Person/Vehicle → Location | directed | movement event |
| ASSOCIATED_WITH | Person → Organization | directed | looser than WORKS_FOR |
| WORKS_FOR | Person → Organization | directed | employment |
| OWNS | Person → Vehicle/Account/Phone | directed | ownership |
| USED | Person → Vehicle/etc. | directed | usage without ownership |
| MENTIONED_IN | Entity → Case/FIR | directed | appears in documents |
| RELATED_TO_CASE | Entity → Case | directed | broader linkage |

## 5. Relationship Provenance (mandatory)

```jsonc
{
  "relationship_id": "rel-00446",   // stable, rel-XXXXX
  "source_id": "person-00012",
  "source_type": "Person",
  "target_id": "account-00009",
  "target_type": "FinancialAccount",
  "relationship_type": "OWNS",
  "timestamp": "2025-03-14T10:22:00Z",  // event time if known, else null
  "confidence": 0.93,                    // 0.0 – 1.0
  "extraction_method": "bank_statement_parse",
  "created_at": "2026-08-26T09:15:00Z"   // record creation (ISO 8601 UTC)
}
```

Validation is enforced by `RelationshipSchema.validate()` and mirrored by
SQL constraints (`CHECK confidence BETWEEN 0 AND 1`, enum types, ISO-8601).

**Referential integrity note:** relationships are polymorphic
(`source_id` may point at any entity table), so PostgreSQL foreign keys
cannot enforce them. Integrity is enforced by:
1. application validation (`ai.schemas`), and
2. the test suite (`tests/test_synthetic_data.py` checks no dangling refs).

## 6. Extraction Contract

Any extractor (rule-based now, ML later) must emit `EntitySchema` /
`RelationshipSchema`. Current rule-based implementations:
`ai/entity_extraction.py`, `ai/relationship_extraction.py`.
Real NER integration is explicitly deferred to a later milestone.
