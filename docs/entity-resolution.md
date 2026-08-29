# Deterministic Entity Resolution — SIH 26189 (Milestone 3)

## Goal

Decide when multiple mentions (from extraction or external records) refer to
the **same canonical entity** in the system, using only **deterministic,
auditable rules**. No probabilistic models, no automatic merges of ambiguous
candidates.

## Core Principles

1. **Exact structured keys auto-link**: phone, account number, vehicle ID
   match ⇒ single candidate, `status="auto_linked"`, confidence=1.0.
2. **Names are inherently ambiguous**: normalized person/org name matches
   ⇒ candidates returned with `status="needs_review"`, confidence=0.60.
3. **No silent merges**: the pipeline never collapses entities; it only
   returns candidates for downstream review/decision.
4. **Declared priors only**: confidence values are fixed constants
   (`DECLARED_NAME_MATCH_CONFIDENCE=0.60`, exact keys=1.0), never learned
   or fabricated per result.

## Match Rules

| Entity Type | Key | Normalization | Auto-link? | Confidence |
|-------------|-----|---------------|------------|------------|
| PhoneNumber | E.164 digits (last 10) | strip non-digits, keep last 10 | yes | 1.0 |
| FinancialAccount | account_number | uppercase, strip spaces | yes | 1.0 |
| Vehicle | registration_number or VIN | uppercase, strip spaces | yes | 1.0 |
| Person | full_name | lowercase, collapse whitespace, strip punctuation | **no** | 0.60 |
| Organization | name | lowercase, drop legal suffixes (pvt ltd, ltd, llp, inc...) | **no** | 0.60 |
| (others) | — | — | no rule yet | — |

## Data Structures

```python
@dataclass
class ResolutionCandidate:
    candidate_entity_id: str      # canonical ID (e.g. person-00042)
    match_method: str             # e.g. "exact_normalized_phone"
    confidence: float             # 1.0 or 0.60
    supporting_fields: List[str]  # which fields supported the match
    status: str                   # "auto_linked" | "needs_review"
```

## EntityIndex

The resolver operates on an `EntityIndex` built from the canonical dataset
(PostgreSQL/Neo4j/synthetic JSON). It maintains:
- `_by_phone`, `_by_account`, `_by_vehicle` → exact lookup tables
- `_by_person_name`, `_by_org_name` → normalized-name lookup tables
- `_records` → full EntityRecord (entity_id, entity_type, display_name)

Construction:
```python
index = EntityIndex.from_dataset(load_synthetic_dataset())
# or incrementally
index.add_person("person-00001", "Rhea Verma")
index.add_organization("org-00001", "Bluepeak Traders Pvt Ltd")
index.add_phone("phone-00001", "+91-901234567")
```

## Usage in Pipeline

```python
from ai.entity_resolution import DeterministicEntityResolver, EntityIndex

resolver = DeterministicEntityResolver(index)

# Resolve a mention from extraction
candidates = resolver.resolve(
    text="Rhea Verma",
    entity_type="Person",
    normalized_value="rhea verma",  # optional pre-normalized
)

# Pipeline integrates automatically:
pipeline = InvestigationPipeline(
    extractor=...,
    resolver=resolver,
    relationship_extractor=...,
)
result = pipeline.run(text, source_id="doc-001")
# result.resolutions maps mention_key → List[ResolutionCandidate]
```

## Output Semantics

| status | Meaning | Downstream action |
|--------|---------|-------------------|
| `auto_linked` | Exactly one candidate on an exact structured key | Safe to attach `entity_id` to mention; proceed to relationship extraction |
| `needs_review` | Multiple candidates or name-based match | **Do not** auto-attach. Flag for human review or downstream disambiguation logic |

## Testing

```python
# Exact phone auto-links
candidates = resolver.resolve("+91-901234567", "PhoneNumber")
assert len(candidates) == 1
assert candidates[0].status == "auto_linked"
assert candidates[0].confidence == 1.0

# Name match always needs review
candidates = resolver.resolve("Rhea Verma", "Person")
assert all(c.status == "needs_review" for c in candidates)
assert candidates[0].confidence == 0.60
```

## Future Extensions (Out of Scope for Milestone 3)

- Probabilistic record linkage (blocking + similarity scoring)
- Learned name disambiguation with embeddings
- Cross-dataset identity fusion
- Automatic merge with human-in-the-loop confirmation

**Milestone 3 stops at deterministic candidates requiring review.**