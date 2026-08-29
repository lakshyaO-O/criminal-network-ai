# Graph Model for Neo4j Mapping

This document maps the canonical model (`docs/data-model.md`,
implemented by `ai/schemas.py` and `db/001_initial_schema.sql`) onto a
Neo4j property graph: 12 node labels, 11 relationship types, mandatory
provenance on every relationship.

## Stable IDs

IDs are **TEXT**, not UUIDs, with the canonical format
`{prefix}-{5-digit counter}` (regex `^[a-z]+-\d{5}$`, e.g. `person-00042`,
`rel-00117`). The same ID always refers to the same entity (idempotent,
upsert-style loading).

Every node carries common properties:

- `entity_id`: String — primary key, equals `<type>_id`
- `<type>_id`: String — convenience alias (e.g. `person_id`)
- `entity_type`: String — label name
- `metadata`: Map (optional)
- `created_at`: DateTime

## Node Labels and Properties

### :Person
- `person_id`: String (format: `person-XXXXX`)
- `full_name`: String (no guilt/criminality fields by design)
- `date_of_birth`: Date (optional)
- `nationality`: String (optional)

### :Organization
- `org_id`: String (format: `org-XXXXX`)
- `name`: String
- `registration_number`: String (optional)
- `jurisdiction`: String (optional)

### :PhoneNumber
- `phone_id`: String (format: `phone-XXXXX`)
- `number`: String (E.164-style, fictional)
- `phone_type`: String (mobile, landline, fax)
- `carrier`: String (optional)

### :Vehicle
- `vehicle_id`: String (format: `vehicle-XXXXX`)
- `registration_number`: String
- `make`: String
- `model`: String
- `year`: Integer
- `color`: String (optional)
- `vin`: String (fictional, optional)

### :Location
- `location_id`: String (format: `location-XXXXX`)
- `latitude`: Float
- `longitude`: Float
- `description`: String (e.g., "Street intersection", "Residence")
- `area_name`: String (optional)
- `metadata.accuracy_meters`: Float (optional)

### :FinancialAccount
- `account_id`: String (format: `account-XXXXX`)
- `account_number`: String (fictional, masked in UIs)
- `account_type`: String (checking, savings, etc.)
- `institution`: String
- `jurisdiction`: String
- `currency`: String

### :Transaction (event-like)
- `transaction_id`: String (format: `transaction-XXXXX`)
- `amount`: Float (Decimal(15,2) upstream)
- `transaction_type`: String (transfer, withdrawal, deposit)
- `currency`: String
- `from_account_id`: String (reference to :FinancialAccount)
- `to_account_id`: String (reference to :FinancialAccount)
- `timestamp`: DateTime
- `is_flagged_demo`: Boolean (demo flag, optional)

### :Communication (event-like)
- `comm_id`: String (format: `comm-XXXXX`)
- `medium`: String (call, sms, email, chat)
- `direction`: String (incoming, outgoing)
- `from_entity_id`: String (polymorphic: :Person or :Organization)
- `to_entity_id`: String (polymorphic: :Person or :Organization)
- `from_phone_id`: String (optional, reference to :PhoneNumber)
- `to_phone_id`: String (optional, reference to :PhoneNumber)
- `timestamp`: DateTime
- `duration_seconds`: Integer (optional)

### :Case
- `case_id`: String (format: `case-XXXXX`)
- `case_number`: String (unique)
- `title`: String
- `description`: String
- `case_type`: String (fraud, theft, etc.)
- `status`: String (open, under_investigation, closed)
- `assigned_to`: String (reference to :Person — investigating officer)
- `opened_at`: DateTime

### :FIR
- `fir_id`: String (format: `fir-XXXXX`)
- `fir_number`: String (unique)
- `case_id`: String (reference to :Case)
- `fir_type`: String (FIR, complaint, intel_report)
- `filed_at`: DateTime
- `filed_by`: String (reference to :Person)
- `jurisdiction`: String

### :Event (observed activity)
- `event_id`: String (format: `event-XXXXX`)
- `name`: String (event name/code)
- `description`: String (optional)
- `event_type`: String (meeting, sighting, handoff, travel)
- `timestamp`: DateTime
- `location_id`: String (reference to :Location)

### :Evidence
- `evidence_id`: String (format: `evidence-XXXXX`)
- `case_id`: String (reference to :Case)
- `description`: String (metadata only — never raw content)
- `evidence_type`: String (document, digital, physical, etc.)
- `source`: String (where evidence was found)
- `collected_at`: DateTime
- `collected_by`: String (reference to :Person)
- `chain_hash`: String (populated by `blockchain/evidence_chain.py`)
- `status`: String (logged, in_custody, under_review)

---

## Relationship Types (canonical set of 11)

Directed unless noted. Self-loops are forbidden.

| Type | From → To | Notes |
|---|---|---|
| KNOWS | Person → Person | symmetric, stored once |
| CALLED | Person → Person | via phones, backed by Communication records |
| TRANSFERRED_TO | Account → Account | backed by Transaction records |
| LOCATED_AT | Entity → Location | current/observed position |
| TRAVELED_TO | Person/Vehicle → Location | movement event |
| ASSOCIATED_WITH | Person → Organization | looser than WORKS_FOR |
| WORKS_FOR | Person → Organization | employment |
| OWNS | Person → Vehicle/Account/Phone | ownership |
| USED | Person → Vehicle/etc. | usage without ownership |
| MENTIONED_IN | Entity → Case/FIR | appears in documents |
| RELATED_TO_CASE | Entity → Case | broader linkage |

## Relationship Provenance Properties (mandatory)

All relationships carry full provenance:

- `relationship_id`: String (stable identifier, format: `rel-XXXXX`)
- `source_id`: String (source entity ID)
- `source_type`: String (entity label name)
- `target_id`: String (target entity ID)
- `target_type`: String (entity label name)
- `relationship_type`: String
- `timestamp`: DateTime (event time if known, else null)
- `confidence`: Float (0–1, extraction confidence)
- `extraction_method`: String (required: pattern, NER model, manual, etc.)
- `created_at`: DateTime (record creation, ISO 8601 UTC)

Example:

```cypher
MATCH (a:Person {entity_id: 'person-00012'})
MATCH (b:FinancialAccount {entity_id: 'account-00009'})
MERGE (a)-[r:OWNS {relationship_id: 'rel-00446'}]->(b)
SET r += {
  source_id: 'person-00012', source_type: 'Person',
  target_id: 'account-00009', target_type: 'FinancialAccount',
  relationship_type: 'OWNS', timestamp: '2025-03-14T10:22:00Z',
  confidence: 0.93, extraction_method: 'bank_statement_parse',
  created_at: '2026-08-26T09:15:00Z'
};
```

### [:KNOWS]
- **From**: Person → **To**: Person (symmetric, stored once)
- **Description**: Person knows another person

### [:CALLED]
- **From**: Person → **To**: Person
- **Description**: Communication between persons via phone numbers;
  backed by :Communication records
- **Example**: `(:Person)-[:CALLED {timestamp: '2024-03-15T14:30:00Z'}]->(:Person)`

### [:TRANSFERRED_TO]
- **From**: FinancialAccount → **To**: FinancialAccount
- **Description**: Funds transferred between accounts; backed by
  :Transaction records

### [:LOCATED_AT]
- **From**: Entity → **To**: Location
- **Description**: Entity was located at a specific location at a time

### [:TRAVELED_TO]
- **From**: Person/Vehicle → **To**: Location
- **Description**: Movement event to a specific location

### [:ASSOCIATED_WITH]
- **From**: Person → **To**: Organization
- **Description**: Looser affiliation than WORKS_FOR
- **Example**: `(:Person)-[:ASSOCIATED_WITH {role: 'member'}]->(:Organization)`

### [:WORKS_FOR]
- **From**: Person → **To**: Organization
- **Description**: Employment

### [:OWNS]
- **From**: Person → **To**: Vehicle/FinancialAccount/PhoneNumber
- **Description**: Ownership of an asset
- **Example**: `(:Person)-[:OWNS {ownership_since: '2022-05-10'}]->(:Vehicle)`

### [:USED]
- **From**: Person → **To**: Vehicle/etc.
- **Description**: Usage without ownership
- **Example**: `(:Person)-[:USED {duration_hours: 2}]->(:Vehicle)`

### [:MENTIONED_IN]
- **From**: Entity → **To**: Case/FIR
- **Description**: Entity appears in documents

### [:RELATED_TO_CASE]
- **From**: Entity → **To**: Case
- **Description**: Broader linkage to a case

---

## Neo4j Index Recommendations

Neo4j does not support indexes on relationships — index node properties
only. Use modern syntax (Neo4j 4.4+); range indexes on `entity_id`
support the MERGE/MATCH patterns above:

```cypher
// Uniqueness-style range indexes on the primary key property
CREATE INDEX person_entity_id_idx IF NOT EXISTS
FOR (p:Person) ON (p.entity_id);
CREATE INDEX org_entity_id_idx IF NOT EXISTS
FOR (o:Organization) ON (o.entity_id);
CREATE INDEX phone_entity_id_idx IF NOT EXISTS
FOR (ph:PhoneNumber) ON (ph.entity_id);
CREATE INDEX vehicle_entity_id_idx IF NOT EXISTS
FOR (v:Vehicle) ON (v.entity_id);
CREATE INDEX location_entity_id_idx IF NOT EXISTS
FOR (l:Location) ON (l.entity_id);
CREATE INDEX account_entity_id_idx IF NOT EXISTS
FOR (fa:FinancialAccount) ON (fa.entity_id);
CREATE INDEX transaction_entity_id_idx IF NOT EXISTS
FOR (t:Transaction) ON (t.entity_id);
CREATE INDEX comm_entity_id_idx IF NOT EXISTS
FOR (c:Communication) ON (c.entity_id);
CREATE INDEX case_entity_id_idx IF NOT EXISTS
FOR (c:Case) ON (c.entity_id);
CREATE INDEX fir_entity_id_idx IF NOT EXISTS
FOR (f:FIR) ON (f.entity_id);
CREATE INDEX event_entity_id_idx IF NOT EXISTS
FOR (e:Event) ON (e.entity_id);
CREATE INDEX evidence_entity_id_idx IF NOT EXISTS
FOR (ev:Evidence) ON (ev.entity_id);

// Property lookups mirroring the SQL indexes on case/fir numbers
CREATE INDEX case_number_idx IF NOT EXISTS
FOR (c:Case) ON (c.case_number);
CREATE INDEX fir_number_idx IF NOT EXISTS
FOR (f:FIR) ON (f.fir_number);
```

---

## Example Graph Query Patterns

### Find a person's network (2-hop):
```cypher
MATCH (person:Person {entity_id: $entity_id})
MATCH path = (person)-[:KNOWS|WORKS_FOR|ASSOCIATED_WITH*1..2]-(related)
RETURN path;
```

### Find communication chain between two persons:
```cypher
MATCH (p1:Person)-[c1:CALLED]-(p2:Person)
WHERE c1.relationship_id IN $comm_rel_ids
RETURN p1, c1, p2;
```

### Find transaction chains between accounts:
```cypher
MATCH path = (acct1:FinancialAccount {entity_id: $from_account})
             -[:TRANSFERRED_TO*1..3]->
             (acct2:FinancialAccount {entity_id: $to_account})
RETURN path;
```

### Find evidence connected to a case:
```cypher
MATCH (c:Case {entity_id: $entity_id})<-[:RELATED_TO_CASE]-(ev:Evidence)
RETURN ev;
```
