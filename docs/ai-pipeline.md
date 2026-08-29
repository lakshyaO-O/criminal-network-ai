# AI Pipeline — SIH 26189 (Milestone 3)

The investigation pipeline is a **composable, stage-oriented** flow that
transforms raw text into validated, persisted entities and relationships,
synchronized to the Neo4j graph. Every stage is independently testable
and replaceable.

## Pipeline Stages

| Stage | Module | Input | Output | Key Contract |
|-------|--------|-------|--------|--------------|
| 1. Preprocessing | `ai.pipeline.InvestigationPipeline.preprocess` | raw text | normalized text | whitespace collapse, keep offsets stable |
| 2. Entity Extraction | `EntityExtractor.extract` | text, source_id | `List[ExtractedEntity]` | `extraction_method` MUST identify engine |
| 3. Entity Resolution | `DeterministicEntityResolver.resolve` | extracted entities | `Dict[mention_key, List[ResolutionCandidate]]` | never auto-merge ambiguous |
| 4. Relationship Extraction | `RelationshipExtractor.extract_relationships` | entities, text, structured_records | `List[RuleRelationship]` | explicit cue/structured source required |
| 5. Validation | `InvestigationPipeline.validate` | `PipelineResult` | `List[str]` errors | confidence bounds, no self-loops, canonical types |
| 6. Persistence | `PersistenceSink.save_*` | validated result | durable storage | in-memory impl for tests, Postgres interface |
| 7. Graph Sync | `GraphRepository.upsert_*` | validated result | Neo4j / in-memory graph | entities first, then relationships |

## Running the Pipeline

```python
from ai.entity_resolution import EntityIndex
from ai.extraction import PatternEntityExtractor
from ai.relationship_rules import RuleBasedRelationshipExtractor
from ai.pipeline import InvestigationPipeline, InMemoryPersistence, InMemoryGraphRepository

# Build index from synthetic dataset
index = EntityIndex.from_dataset(load_synthetic_dataset())

# Compose pipeline
pipeline = InvestigationPipeline(
    extractor=PatternEntityExtractor(known_entities=index),
    resolver=DeterministicEntityResolver(index),
    relationship_extractor=RuleBasedRelationshipExtractor(),
    persistence=InMemoryPersistence(),
    graph_repository=InMemoryGraphRepository(),
)

# Execute
result = pipeline.run(
    raw_text="Rhea Verma works for Bluepeak Traders Pvt Ltd.",
    source_id="doc-001",
    do_persist=True,
    do_sync=True,
)
```

## Stage Independence

Each stage is a public method on `InvestigationPipeline`:
- `preprocess(raw_text) -> str`
- `extract_entities(text, source_id) -> List[ExtractedEntity]`
- `resolve_entities(entities) -> Dict[str, List[ResolutionCandidate]]`
- `extract_relationships(entities, text, source_id, structured_records) -> List[RuleRelationship]`
- `validate(result) -> List[str]`
- `persist(result)` / `sync_graph(result)`

Tests call stages individually; no hidden state between stages.

## ExtractedEntity Contract

```python
@dataclass
class ExtractedEntity:
    text: str                          # surface form
    entity_type: str                   # one of 12 canonical types
    start_offset: int
    end_offset: int
    normalized_value: Optional[str]    # for matching/resolution
    entity_id: Optional[str]           # canonical ID if already known
    confidence: Optional[float]        # NEVER fabricated
    extraction_method: str             # "pattern:phone_fictional" | "spacy:en_core_web_sm:PERSON"
    source_id: Optional[str]
    metadata: Dict[str, Any]
```

**Confidence policy (Milestone 3):**
- Pattern rules: fixed declared priors in `RULE_PRIORS` (e.g., `phone_fictional=0.95`).
- spaCy NER: `confidence=None` (model gives label, not calibrated score).
- No per-result fabrication.

## Entity Resolution Contract

```python
@dataclass
class ResolutionCandidate:
    candidate_entity_id: str
    match_method: str                 # "exact_normalized_phone", "normalized_person_name", ...
    confidence: float                 # 1.0 for exact structured keys; DECLARED_NAME_MATCH for names
    supporting_fields: List[str]
    status: str                       # "auto_linked" | "needs_review"
```

**Deterministic rules only:**
- Exact normalized phone → auto-linked
- Exact account number → auto-linked
- Exact vehicle identifier → auto-linked
- Normalized person/org name → always `needs_review` (inherently ambiguous)

## Relationship Extraction Contract

```python
@dataclass
class RuleRelationship:
    relationship_id: str              # rel-XXXXX
    source_entity_id: Optional[str]
    source_type: str
    source_text: str
    target_entity_id: Optional[str]
    target_type: str
    target_text: str
    relationship_type: str            # one of 11 canonical
    confidence: float                 # fixed rule prior
    extraction_method: str            # "rule:works_for_cue" | "rule:transferred_to_structured"
    timestamp: Optional[str]
    source_id: Optional[str]
    metadata: Dict[str, Any]
```

**Rule design:**
- Cue-driven (regex window between two mentions) for text sources.
- Structured records (transactions, events) produce authoritative relationships without text cues.
- Every rule declares a fixed prior in `RULE_PRIORS`.

## Safety

- No stage assigns guilt, criminality, or risk verdicts.
- Neutral terminology only in analytical output.
- All provenance preserved through to Neo4j.

## Extensibility

| New capability | Where to add |
|----------------|--------------|
| Transformer NER | new `EntityExtractor` impl (e.g. `TransformerEntityExtractor`) |
| Probabilistic resolution | new `EntityResolver` impl; pipeline accepts any `DeterministicEntityResolver` subclass |
| Learned relationship extraction | new `RelationshipExtractor` impl |
| PostgreSQL persistence | implement `PersistenceSink` using `asyncpg`/`psycopg` |
| Neo4j sync | already abstracted via `GraphRepository` protocol |