"""FastAPI routes — Milestone 3 endpoints."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings, create_persistence, load_known_entities, load_synthetic_dataset
from app.graph import GraphRepository, InMemoryGraphRepository
from app.schemas import (
    AnalysisResponse,
    BridgeDetailOut,
    CaseOut,
    CentralityResponse,
    CommunityDetailOut,
    EntityOut,
    EntityRelationshipsOut,
    ExtractedEntityOut,
    ExtractionRequest,
    ExtractionResponse,
    HealthResponse,
    IndicatorOut,
    IndicatorsResponse,
    InvestigationEvidenceOut,
    InvestigationFindingOut,
    InvestigationFindingsResponse,
    InvestigationPathRequest,
    InvestigationPathResponse,
    InvestigationSnapshotRequest,
    InvestigationSnapshotResponse,
    InvestigationSubgraphRequest,
    InvestigationSubgraphResponse,
    NeighborhoodOut,
    NetworkOut,
    PipelineRequest,
    PipelineResponse,
    RelationshipExtractionRequest,
    RelationshipExtractionResponse,
    RelationshipOut,
    RelationshipStrengthOut,
    ResolutionCandidateOut,
    ShortestPathOut,
    StructuredIndicatorOut,
    TemporalIndicatorOut,
    TransactionChainOut,
)
from app.services.network_analysis import (
    analyze_network,
    analyze_graph,
    compute_centrality,
    find_communities,
    find_bridges,
    compute_relationship_strength,
    analyze_temporal,
    find_transaction_chains,
    generate_indicators,
)
from app.services.investigation import (
    investigation_subgraph,
    investigation_path,
    generate_findings,
    investigation_snapshot,
)
from app.services import audit as audit_service
from ai.entity_resolution import DeterministicEntityResolver, EntityIndex
from ai.extraction import PatternEntityExtractor, SpacyEntityExtractor
from ai.pipeline import InvestigationPipeline, InMemoryPersistence
from ai.relationship_rules import RuleBasedRelationshipExtractor

router = APIRouter(prefix="/api", tags=["api"])

# --- Global singletons (built at startup) ------------------------------------

_known_entities: Optional[EntityIndex] = None
_dataset: Dict[str, Any] = {}
_graph_repo: Optional[GraphRepository] = None
_persistence: Any = None  # PersistenceBase (Postgres or In-Memory) — set in startup
_persistence_health: Dict[str, str] = {"postgresql": "disconnected", "neo4j": "disconnected"}


def get_known_entities() -> EntityIndex:
    if _known_entities is None:
        raise HTTPException(status_code=503, detail="Entity index not loaded")
    return _known_entities


def get_dataset() -> Dict[str, Any]:
    return _dataset


def get_graph_repo() -> GraphRepository:
    if _graph_repo is None:
        raise HTTPException(status_code=503, detail="Graph repository not loaded")
    return _graph_repo


def get_persistence():
    if _persistence is None:
        raise HTTPException(status_code=503, detail="Persistence not loaded")
    return _persistence


def build_extractor(use_spacy: bool) -> Any:
    if use_spacy:
        try:
            return SpacyEntityExtractor(known_entities=_known_entities)
        except Exception:
            pass  # fall back to pattern
    return PatternEntityExtractor(known_entities=_known_entities)


def _to_relationship_out(rel: Dict[str, Any]) -> RelationshipOut:
    """Convert flat graph repo relationship or nested rule relationship to RelationshipOut."""
    if "source" in rel and isinstance(rel.get("source"), dict):
        # Already nested (from RuleRelationship.to_dict or structured)
        return RelationshipOut(**rel)
    # Flat storage from InMemoryGraphRepository / Neo4j: source_id/source_type etc.
    source = {
        "entity_id": rel.get("source_id"),
        "entity_type": rel.get("source_type"),
        "text": rel.get("source_text") or rel.get("source_id") or "",
    }
    target = {
        "entity_id": rel.get("target_id"),
        "entity_type": rel.get("target_type"),
        "text": rel.get("target_text") or rel.get("target_id") or "",
    }
    return RelationshipOut(
        relationship_id=rel.get("relationship_id", ""),
        source=source,
        target=target,
        relationship_type=rel.get("relationship_type", "RELATED_TO_CASE"),
        timestamp=rel.get("timestamp"),
        confidence=float(rel.get("confidence", 0.5)),
        extraction_method=rel.get("extraction_method", "unknown"),
        source_id=rel.get("source_id"),
        metadata=rel.get("metadata", {}),
    )


# --- Startup / Shutdown -------------------------------------------------------

async def startup():
    global _known_entities, _dataset, _graph_repo, _persistence, _persistence_health
    _dataset = load_synthetic_dataset(settings.data_dir)
    _known_entities = load_known_entities(settings.data_dir)

    # Persistence: PostgreSQL if reachable, else in-memory (tests / local dev without DB)
    _persistence = create_persistence()
    try:
        # Verify actual connectivity for health — distinguish PostgreSQL vs in-memory fallback
        from ai.persistence.postgres import PostgresPersistence as _PGClass  # type: ignore

        is_postgres = isinstance(_persistence, _PGClass)
        if is_postgres and hasattr(_persistence, "health_check"):
            _persistence_health["postgresql"] = "connected" if _persistence.health_check() else "disconnected"
        elif is_postgres:
            _persistence_health["postgresql"] = "connected"
        else:
            # In-memory fallback — report as in_memory so health is truthful
            _persistence_health["postgresql"] = "in_memory"
    except Exception:
        _persistence_health["postgresql"] = "disconnected"

    # Try Neo4j, else in-memory graph
    neo4j_repo = None
    if os.getenv("NEO4J_ENABLED", "true").lower() == "true":
        try:
            from app.graph import Neo4jGraphRepository  # type: ignore

            neo4j_repo = Neo4jGraphRepository(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
            _persistence_health["neo4j"] = "connected"
        except Exception:
            neo4j_repo = None
            _persistence_health["neo4j"] = "disconnected"
    else:
        _persistence_health["neo4j"] = "disabled"

    # Build graph repo from synthetic dataset (in-memory or Neo4j depending on availability)
    if neo4j_repo is not None:
        repo: GraphRepository = neo4j_repo
        # Sync synthetic dataset into Neo4j (idempotent MERGEs)
        for key, rows in _dataset.items():
            if key in ("generation_config", "relationships"):
                continue
            if not isinstance(rows, list):
                continue
            for row in rows:
                eid = row.get("entity_id")
                etype = row.get("entity_type")
                if eid and etype:
                    try:
                        repo.upsert_entity(eid, etype, row)
                    except Exception:
                        pass
        for rel in _dataset.get("relationships", []):
            try:
                repo.upsert_relationship(
                    rel["relationship_id"],
                    rel["source_id"], rel["source_type"],
                    rel["target_id"], rel["target_type"],
                    rel["relationship_type"],
                    {k: v for k, v in rel.items() if k not in (
                        "source_id", "source_type", "target_id", "target_type",
                        "relationship_type", "relationship_id")},
                )
            except Exception:
                pass
    else:
        repo = InMemoryGraphRepository()
        # Upsert entities — use canonical entity_id/entity_type directly
        for key, rows in _dataset.items():
            if key in ("generation_config", "relationships"):
                continue
            if not isinstance(rows, list):
                continue
            for row in rows:
                eid = row.get("entity_id")
                etype = row.get("entity_type")
                if eid and etype:
                    repo.upsert_entity(eid, etype, row)
        # Upsert relationships
        for rel in _dataset.get("relationships", []):
            repo.upsert_relationship(
                rel["relationship_id"],
                rel["source_id"], rel["source_type"],
                rel["target_id"], rel["target_type"],
                rel["relationship_type"],
                {k: v for k, v in rel.items() if k not in (
                    "source_id", "source_type", "target_id", "target_type",
                    "relationship_type", "relationship_id")},
            )
    _graph_repo = repo


# --- Routes ------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    # Verify Neo4j connectivity actually (not just env flag)
    neo4j_status = _persistence_health.get("neo4j", "disconnected")
    # Re-verify on each health call if not connected (in case DB came up)
    if neo4j_status != "connected" and os.getenv("NEO4J_ENABLED", "true").lower() == "true":
        try:
            from app.graph import Neo4jGraphRepository  # type: ignore

            repo = Neo4jGraphRepository(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
            repo.close()
            neo4j_status = "connected"
            _persistence_health["neo4j"] = "connected"
        except Exception:
            neo4j_status = "disconnected"
            _persistence_health["neo4j"] = "disconnected"

    pg_status = _persistence_health.get("postgresql", "disconnected")
    # Live verification for PostgreSQL if currently disconnected but persistence exists
    if pg_status == "disconnected" and _persistence is not None and hasattr(_persistence, "health_check"):
        try:
            pg_status = "connected" if _persistence.health_check() else "disconnected"
            _persistence_health["postgresql"] = pg_status
        except Exception:
            pg_status = "disconnected"

    # Legacy boolean for backwards compat
    neo4j_connected: Optional[bool] = None
    if os.getenv("NEO4J_ENABLED") is not None:
        neo4j_connected = neo4j_status == "connected"
    else:
        # If env not set, still report based on actual check
        neo4j_connected = neo4j_status == "connected" if neo4j_status != "disabled" else None

    return HealthResponse(
        status="ok",
        service="criminal-network-analysis",
        version="1.0.0",
        neo4j_connected=neo4j_connected,
        database={"postgresql": pg_status},
        graph={"neo4j": neo4j_status},
    )


@router.post("/extraction/entities", response_model=ExtractionResponse)
async def extract_entities(
    request: ExtractionRequest,
    index: EntityIndex = Depends(get_known_entities),
) -> ExtractionResponse:
    extractor = build_extractor(request.use_spacy)
    entities = extractor.extract(request.text, source_id=request.source_id)
    return ExtractionResponse(
        source_id=request.source_id,
        entities=[ExtractedEntityOut(**e.to_dict()) for e in entities],
        entity_count=len(entities),
    )


@router.post("/extraction/relationships", response_model=RelationshipExtractionResponse)
async def extract_relationships(
    request: RelationshipExtractionRequest,
    index: EntityIndex = Depends(get_known_entities),
) -> RelationshipExtractionResponse:
    # Build entities from request if provided; if none, extract automatically
    from ai.extraction.base import ExtractedEntity
    entities = [
        ExtractedEntity(**{k: v for k, v in e.model_dump().items() if k != "metadata"})
        for e in request.entities
    ]
    # Auto-extract if caller provided no pre-extracted entities (common in tests)
    if not entities and request.text:
        # Use pattern extractor with known entities for deterministic results
        auto_extractor = PatternEntityExtractor(known_entities=index)
        entities = auto_extractor.extract(request.text, source_id=request.source_id)
    extractor = RuleBasedRelationshipExtractor()
    rels = extractor.extract_relationships(
        entities,
        request.text,
        source_id=request.source_id,
        structured_records=request.structured_records,
    )
    return RelationshipExtractionResponse(
        source_id=request.source_id,
        relationships=[RelationshipOut(**r.to_dict()) for r in rels],
        relationship_count=len(rels),
    )


@router.post("/investigations/analyze", response_model=PipelineResponse)
async def run_pipeline(
    request: PipelineRequest,
    index: EntityIndex = Depends(get_known_entities),
    graph_repo: GraphRepository = Depends(get_graph_repo),
    persistence: InMemoryPersistence = Depends(get_persistence),
) -> PipelineResponse:
    extractor = build_extractor(request.use_spacy)
    resolver = DeterministicEntityResolver(index)
    rel_extractor = RuleBasedRelationshipExtractor()

    pipeline = InvestigationPipeline(
        extractor=extractor,
        resolver=resolver,
        relationship_extractor=rel_extractor,
        persistence=persistence,
        graph_repository=graph_repo,
    )

    result = pipeline.run(
        raw_text=request.text,
        source_id=request.source_id,
        structured_records=request.structured_records,
        do_persist=request.persist,
        do_sync=request.sync_graph,
    )
    return PipelineResponse(
        source_id=result.source_id,
        preprocessed_text=result.preprocessed_text,
        entities=[ExtractedEntityOut(**e.to_dict()) for e in result.entities],
        resolutions={
            k: [ResolutionCandidateOut(**c.to_dict()) for c in v]
            for k, v in result.resolutions.items()
        },
        relationships=[RelationshipOut(**r.to_dict()) for r in result.relationships],
        validation_errors=result.validation_errors,
        persisted={
            "entities": result.persisted_entities,
            "relationships": result.persisted_relationships,
        },
        graph_sync={
            "nodes": result.graph_nodes_upserted,
            "relationships": result.graph_relationships_upserted,
        },
    )


@router.get("/entities/{entity_id}", response_model=EntityOut)
async def get_entity(
    entity_id: str,
    dataset: Dict[str, Any] = Depends(get_dataset),
) -> EntityOut:
    # Prefer canonical PostgreSQL store if available and healthy
    if _persistence is not None and hasattr(_persistence, "get_entity"):
        try:
            pg_entity = _persistence.get_entity(entity_id)  # type: ignore
            if pg_entity:
                # Map PostgreSQL row to EntityOut fields (handle different table schemas)
                # Normalize to EntityOut expected keys
                mapped = {
                    "entity_id": pg_entity.get("entity_id") or entity_id,
                    "entity_type": pg_entity.get("entity_type") or pg_entity.get("entity_type") or _infer_entity_type(entity_id),
                    "full_name": pg_entity.get("full_name"),
                    "name": pg_entity.get("name"),
                    "number": pg_entity.get("number"),
                    "registration_number": pg_entity.get("registration_number"),
                    "account_number": pg_entity.get("account_number"),
                    "case_number": pg_entity.get("case_number"),
                    "fir_number": pg_entity.get("fir_number"),
                    "title": pg_entity.get("title"),
                    "status": pg_entity.get("status"),
                    "created_at": str(pg_entity.get("created_at")) if pg_entity.get("created_at") else None,
                    "metadata": pg_entity.get("metadata") if isinstance(pg_entity.get("metadata"), dict) else {},
                }
                # If entity_type still missing, use dataset fallback
                if not mapped["entity_type"]:
                    mapped["entity_type"] = _infer_entity_type(entity_id) or "Person"
                return EntityOut(**{k: v for k, v in mapped.items() if v is not None or k in ("entity_id", "entity_type")})
        except Exception:
            pass  # fall through to dataset

    for key, rows in dataset.items():
        if key == "generation_config":
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if row.get("entity_id") == entity_id:
                return EntityOut(**row)
            # Fallback for legacy id field naming (kept for backwards compatibility)
            pk = f"{key.rstrip('s')}_id"
            if row.get(pk) == entity_id:
                return EntityOut(**row)
    raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")


def _infer_entity_type(entity_id: str) -> str:
    prefix = entity_id.split("-")[0] if "-" in entity_id else ""
    mapping = {
        "person": "Person",
        "org": "Organization",
        "phone": "PhoneNumber",
        "vehicle": "Vehicle",
        "location": "Location",
        "account": "FinancialAccount",
        "transaction": "Transaction",
        "comm": "Communication",
        "case": "Case",
        "fir": "FIR",
        "event": "Event",
        "evidence": "Evidence",
    }
    return mapping.get(prefix, "Person")


@router.get("/entities/{entity_id}/relationships", response_model=EntityRelationshipsOut)
async def get_entity_relationships(
    entity_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
) -> EntityRelationshipsOut:
    rels = graph_repo.get_relationships(entity_id)
    return EntityRelationshipsOut(
        entity_id=entity_id,
        relationships=[_to_relationship_out(r) for r in rels],
    )


@router.get("/entities/{entity_id}/neighborhood", response_model=NeighborhoodOut)
async def get_neighborhood(
    entity_id: str,
    depth: int = 1,
    graph_repo: GraphRepository = Depends(get_graph_repo),
) -> NeighborhoodOut:
    if depth < 1 or depth > 6:
        raise HTTPException(status_code=400, detail="depth must be 1..6")
    return NeighborhoodOut(**graph_repo.neighborhood(entity_id, depth=depth))


@router.get("/cases/{case_id}", response_model=CaseOut)
async def get_case(
    case_id: str,
    dataset: Dict[str, Any] = Depends(get_dataset),
) -> CaseOut:
    if _persistence is not None and hasattr(_persistence, "get_case"):
        try:
            pg_case = _persistence.get_case(case_id)  # type: ignore
            if pg_case:
                # Normalize PostgreSQL row to CaseOut
                return CaseOut(
                    case_id=pg_case.get("case_id", case_id),
                    case_number=pg_case.get("case_number", case_id),
                    title=pg_case.get("title", "Untitled"),
                    description=pg_case.get("description") or "",
                    case_type=pg_case.get("case_type") or "unknown",
                    status=str(pg_case.get("status") or "open"),
                    assigned_to=pg_case.get("assigned_to"),
                    opened_at=str(pg_case.get("opened_at")) if pg_case.get("opened_at") else None,
                    metadata=pg_case.get("metadata") if isinstance(pg_case.get("metadata"), dict) else {},
                )
        except Exception:
            pass
    for row in dataset.get("cases", []):
        if row.get("case_id") == case_id:
            return CaseOut(**row)
    raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")


@router.get("/network/{case_id}", response_model=NetworkOut)
async def get_network(
    case_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
) -> NetworkOut:
    # Find the case
    case = None
    for row in dataset.get("cases", []):
        if row.get("case_id") == case_id:
            case = row
            break
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    # Collect related entities via RELATED_TO_CASE / MENTIONED_IN
    rels = graph_repo.get_relationships(case_id)
    related_ids = set()
    for rel in rels:
        if rel["relationship_type"] in ("RELATED_TO_CASE", "MENTIONED_IN"):
            related_ids.add(rel["source_id"])
            related_ids.add(rel["target_id"])

    entities = []
    for eid in related_ids:
        ent = graph_repo.get_entity(eid)
        if ent:
            entities.append(EntityOut(**ent))

    network_rels = []
    seen_rel_ids: set = set()
    for eid in related_ids:
        for rel in graph_repo.get_relationships(eid):
            if rel["source_id"] in related_ids and rel["target_id"] in related_ids:
                rid = rel.get("relationship_id")
                if rid in seen_rel_ids:
                    continue
                seen_rel_ids.add(rid)
                network_rels.append(_to_relationship_out(rel))

    stats = graph_repo.statistics().to_dict()
    return NetworkOut(
        case_id=case_id,
        entities=entities,
        relationships=network_rels,
        statistics=stats,
    )


@router.get("/analysis", response_model=AnalysisResponse)
async def analyze(
    graph_repo: GraphRepository = Depends(get_graph_repo),
) -> AnalysisResponse:
    entities_snapshot, relationships_snapshot = graph_repo.export_snapshot()
    result = analyze_network(entities_snapshot, relationships_snapshot)
    return AnalysisResponse(**result)


# --- Milestone 5: Graph Intelligence extended endpoints --------------------

def _get_snapshot(graph_repo: GraphRepository):
    entities_snapshot, relationships_snapshot = graph_repo.export_snapshot()
    return entities_snapshot, relationships_snapshot


@router.get("/analysis/centrality", tags=["analysis"])
async def get_centrality(graph_repo: GraphRepository = Depends(get_graph_repo)):
    entities, rels = _get_snapshot(graph_repo)
    centrality = compute_centrality(entities, rels)
    return {
        "centrality": centrality,
        "explanations": {
            "degree": "Number of direct connections relative to graph size (degree/(n-1)). High degree means many direct observations.",
            "betweenness": "Frequency entity lies on shortest paths. High betweenness indicates bridging multiple regions.",
            "closeness": "Inverse average distance to all reachable nodes.",
            "pagerank": "Link-analysis score (damping 0.85). High PageRank indicates well-connected via important neighbors.",
        },
    }


@router.get("/analysis/communities", tags=["analysis"])
async def get_communities(graph_repo: GraphRepository = Depends(get_graph_repo)):
    entities, rels = _get_snapshot(graph_repo)
    comms = find_communities(entities, rels)
    return {"communities": comms, "count": len(comms)}


@router.get("/analysis/bridges", tags=["analysis"])
async def get_bridges(graph_repo: GraphRepository = Depends(get_graph_repo)):
    entities, rels = _get_snapshot(graph_repo)
    bridges = find_bridges(entities, rels, top_k=10)
    return {"bridges": bridges, "count": len(bridges)}


@router.get("/analysis/temporal", tags=["analysis"])
async def get_temporal(graph_repo: GraphRepository = Depends(get_graph_repo)):
    _, rels = _get_snapshot(graph_repo)
    indicators = analyze_temporal(rels)
    return {"temporal_indicators": indicators, "count": len(indicators)}


@router.get("/analysis/transaction-chains", tags=["analysis"])
async def get_transaction_chains(graph_repo: GraphRepository = Depends(get_graph_repo)):
    _, rels = _get_snapshot(graph_repo)
    chains = find_transaction_chains(rels)
    return {"transaction_chains": chains, "count": len(chains)}


@router.get("/analysis/relationship-strength", tags=["analysis"])
async def get_relationship_strength(graph_repo: GraphRepository = Depends(get_graph_repo)):
    _, rels = _get_snapshot(graph_repo)
    strengths = compute_relationship_strength(rels)
    return {"relationship_strength": strengths[:50], "count": len(strengths)}


@router.get("/analysis/indicators", tags=["analysis"])
async def get_indicators(graph_repo: GraphRepository = Depends(get_graph_repo)):
    entities, rels = _get_snapshot(graph_repo)
    indicators = generate_indicators(entities, rels)
    return {"indicators": indicators, "count": len(indicators)}


@router.get("/analysis/path", tags=["analysis"])
async def get_path(
    source_id: str,
    target_id: str,
    max_depth: int = 6,
    graph_repo: GraphRepository = Depends(get_graph_repo),
):
    if max_depth < 1 or max_depth > 6:
        raise HTTPException(status_code=400, detail="max_depth must be 1..6")
    # Validate entities exist
    if not graph_repo.get_entity(source_id):
        raise HTTPException(status_code=404, detail=f"Source entity '{source_id}' not found")
    if not graph_repo.get_entity(target_id):
        raise HTTPException(status_code=404, detail=f"Target entity '{target_id}' not found")
    result = graph_repo.shortest_path(source_id, target_id, max_depth=max_depth)
    if result is None:
        raise HTTPException(status_code=500, detail="Path computation failed")
    return result


@router.get("/analysis/entities/{entity_id}", tags=["analysis"])
async def analyze_entity(
    entity_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
):
    if not graph_repo.get_entity(entity_id):
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    entities, rels = _get_snapshot(graph_repo)
    # Single-entity context: centrality for this entity, its neighborhood, and indicators involving it
    centrality = compute_centrality(entities, rels)
    entity_centrality = {
        "degree": centrality["degree"].get(entity_id, 0.0),
        "betweenness": centrality["betweenness"].get(entity_id, 0.0),
        "closeness": centrality["closeness"].get(entity_id, 0.0),
        "pagerank": centrality["pagerank"].get(entity_id, 0.0),
    }
    # Neighborhood depth 1
    try:
        neighborhood = graph_repo.neighborhood(entity_id, depth=1)
    except Exception:
        neighborhood = {"nodes": [], "edges": []}
    all_indicators = generate_indicators(entities, rels)
    entity_indicators = [ind for ind in all_indicators if entity_id in ind.get("entity_ids", [])]
    return {
        "entity_id": entity_id,
        "centrality": entity_centrality,
        "centrality_explanations": {
            "degree": "Direct connections relative to graph size.",
            "betweenness": "Frequency on shortest paths.",
            "closeness": "Inverse average distance to others.",
            "pagerank": "Link-analysis score.",
        },
        "neighborhood": neighborhood,
        "indicators": entity_indicators,
    }


@router.get("/analysis/entities/{entity_id}/centrality", tags=["analysis"])
async def get_entity_centrality(
    entity_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
):
    if not graph_repo.get_entity(entity_id):
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    entities, rels = _get_snapshot(graph_repo)
    centrality = compute_centrality(entities, rels)
    return {
        "entity_id": entity_id,
        "centrality": {
            "degree": centrality["degree"].get(entity_id, 0.0),
            "betweenness": centrality["betweenness"].get(entity_id, 0.0),
            "closeness": centrality["closeness"].get(entity_id, 0.0),
            "pagerank": centrality["pagerank"].get(entity_id, 0.0),
        },
        "explanations": {
            "degree": "Direct connections relative to graph size.",
            "betweenness": "Frequency on shortest paths between others.",
            "closeness": "Inverse average distance to reachable nodes.",
            "pagerank": "Link-analysis score (damping 0.85).",
        },
    }


@router.get("/analysis/entities/{entity_id}/neighborhood", tags=["analysis"])
async def get_analysis_entity_neighborhood(
    entity_id: str,
    depth: int = 1,
    graph_repo: GraphRepository = Depends(get_graph_repo),
):
    if depth < 1 or depth > 6:
        raise HTTPException(status_code=400, detail="depth must be 1..6")
    if not graph_repo.get_entity(entity_id):
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    return graph_repo.neighborhood(entity_id, depth=depth)


@router.get("/analysis/{case_id}", response_model=AnalysisResponse)
async def analyze_case(
    case_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
) -> AnalysisResponse:
    # Subgraph for a case — must be last to avoid shadowing /analysis/* specific routes
    case_rel = graph_repo.get_relationships(case_id)
    # If case_id is actually a known analysis sub-path, return 404 quickly (defensive)
    if case_id in ("centrality", "communities", "bridges", "temporal", "indicators", "transaction-chains", "relationship-strength", "path", "entities"):
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    related = {case_id}
    for rel in case_rel:
        if rel["relationship_type"] in ("RELATED_TO_CASE", "MENTIONED_IN"):
            related.add(rel["source_id"])
            related.add(rel["target_id"])
    # If no related entities and case not in dataset, ensure 404 for truly unknown case
    if len(related) == 1:
        found = any(row.get("case_id") == case_id for row in dataset.get("cases", []))
        if not found:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    entities = {eid: (graph_repo.get_entity(eid)["entity_type"], graph_repo.get_entity(eid)) for eid in related if graph_repo.get_entity(eid)}
    rels = []
    for eid in related:
        for rel in graph_repo.get_relationships(eid):
            if rel["source_id"] in related and rel["target_id"] in related:
                rels.append(rel)
    result = analyze_network(entities, rels)
    return AnalysisResponse(**result)


# ---------------------------------------------------------------------------
# Investigation Engine — Milestone 8A
# ---------------------------------------------------------------------------

@router.get("/investigations/subgraph", response_model=InvestigationSubgraphResponse, tags=["investigations"])
async def get_investigation_subgraph(
    root_entity_id: str,
    depth: int = 1,
    case_id: Optional[str] = None,
    entity_types: Optional[str] = None,
    relationship_types: Optional[str] = None,
    max_nodes: int = 200,
    max_relationships: int = 400,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    """Investigator-focused subgraph: case → root → N-hop → filtered, bounded, deterministic."""
    # Parse comma-separated filters
    ent_filter = [s.strip() for s in entity_types.split(",") if s.strip()] if entity_types else None
    rel_filter = [s.strip() for s in relationship_types.split(",") if s.strip()] if relationship_types else None
    try:
        result = investigation_subgraph(
            graph_repo, dataset, root_entity_id, depth=depth, case_id=case_id,
            entity_types=ent_filter, relationship_types=rel_filter,
            max_nodes=max_nodes, max_relationships=max_relationships,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(
        event_type="investigation_created",
        analysis_type="subgraph",
        case_id=case_id,
        root_entity_id=root_entity_id,
        object_id=result.get("root_entity", {}).get("entity_id"),
        parameters={"depth": depth, "max_nodes": max_nodes, "entity_types": ent_filter, "relationship_types": rel_filter},
        status="completed",
    )
    return InvestigationSubgraphResponse(**result)


@router.post("/investigations/subgraph", response_model=InvestigationSubgraphResponse, tags=["investigations"])
async def post_investigation_subgraph(
    request: InvestigationSubgraphRequest,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = investigation_subgraph(
            graph_repo, dataset, request.root_entity_id, depth=request.depth, case_id=request.case_id,
            entity_types=request.entity_types, relationship_types=request.relationship_types,
            max_nodes=request.max_nodes, max_relationships=request.max_relationships,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(
        event_type="investigation_created",
        analysis_type="subgraph",
        case_id=request.case_id,
        root_entity_id=request.root_entity_id,
        parameters={"depth": request.depth, "max_nodes": request.max_nodes},
        status="completed",
    )
    return InvestigationSubgraphResponse(**result)


@router.get("/investigations/paths", response_model=InvestigationPathResponse, tags=["investigations"])
async def get_investigation_paths(
    source_id: str,
    target_id: str,
    max_depth: int = 6,
    case_id: Optional[str] = None,
    relationship_types: Optional[str] = None,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    rel_filter = [s.strip() for s in relationship_types.split(",") if s.strip()] if relationship_types else None
    try:
        result = investigation_path(
            graph_repo, dataset, source_id, target_id, max_depth=max_depth, case_id=case_id, relationship_types=rel_filter
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(
        event_type="investigation_created",
        analysis_type="path",
        case_id=case_id,
        entity_id=source_id,
        object_id=f"{source_id}->{target_id}",
        parameters={"max_depth": max_depth, "relationship_types": rel_filter},
        status="completed" if result.get("found") else "no_path",
    )
    return InvestigationPathResponse(**result)


@router.post("/investigations/paths", response_model=InvestigationPathResponse, tags=["investigations"])
async def post_investigation_paths(
    request: InvestigationPathRequest,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = investigation_path(
            graph_repo, dataset, request.source_id, request.target_id, max_depth=request.max_depth,
            case_id=request.case_id, relationship_types=request.relationship_types
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(
        event_type="investigation_created",
        analysis_type="path",
        case_id=request.case_id,
        entity_id=request.source_id,
        object_id=f"{request.source_id}->{request.target_id}",
        parameters={"max_depth": request.max_depth},
        status="completed" if result.get("found") else "no_path",
    )
    return InvestigationPathResponse(**result)


@router.get("/investigations/findings", response_model=InvestigationFindingsResponse, tags=["investigations"])
async def get_investigation_findings(
    case_id: Optional[str] = None,
    root_entity_id: Optional[str] = None,
    depth: int = 2,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    if depth < 0 or depth > 6:
        raise HTTPException(status_code=400, detail="depth must be 0..6")
    # Build context: if root provided, use its subgraph; else full graph or case network
    if root_entity_id:
        try:
            subgraph = investigation_subgraph(graph_repo, dataset, root_entity_id, depth=depth, case_id=case_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        snapshot_entities = {e.get("entity_id"): (e.get("entity_type", "Unknown"), e) for e in subgraph["entities"] if e.get("entity_id")}
        relationships = subgraph["relationships"]
        # Generate findings from subgraph context
        findings = generate_findings(case_id, root_entity_id, subgraph, [], snapshot_entities, relationships)
    else:
        # Global or case-level findings
        if case_id:
            # Case network
            case_rels = graph_repo.get_relationships(case_id)
            related = {case_id}
            for rel in case_rels:
                if rel.get("relationship_type") in ("RELATED_TO_CASE", "MENTIONED_IN"):
                    related.add(rel.get("source_id"))
                    related.add(rel.get("target_id"))
            if len(related) == 1 and not any(row.get("case_id") == case_id for row in dataset.get("cases", [])):
                raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
            entities = {eid: (graph_repo.get_entity(eid)["entity_type"], graph_repo.get_entity(eid)) for eid in related if graph_repo.get_entity(eid)}
            rels = []
            for eid in related:
                for rel in graph_repo.get_relationships(eid):
                    if rel.get("source_id") in related and rel.get("target_id") in related:
                        rels.append(rel)
            findings = generate_findings(case_id, None, {"entities": [], "relationships": rels}, [], entities, rels)
        else:
            # Global
            entities_snap, rels_snap = graph_repo.export_snapshot()
            findings = generate_findings(None, None, {"entities": [], "relationships": rels_snap}, [], entities_snap, rels_snap)

    # Ensure deterministic ordering already in generate_findings; limit
    findings = sorted(findings, key=lambda f: f["finding_id"])[:20]
    audit_service.record_event(
        event_type="finding_generated",
        analysis_type="findings",
        case_id=case_id,
        root_entity_id=root_entity_id,
        parameters={"depth": depth, "count": len(findings)},
        status="completed",
    )
    return InvestigationFindingsResponse(
        case_id=case_id,
        root_entity_id=root_entity_id,
        findings=[InvestigationFindingOut(**f) for f in findings],
        count=len(findings),
        provenance=[{"source": "investigation_engine", "analysis_type": "findings", "timestamp": "2024-01-01T00:00:00Z"}],
    )


@router.get("/investigations/evidence", response_model=List[InvestigationEvidenceOut], tags=["investigations"])
async def get_investigation_evidence(
    case_id: Optional[str] = None,
    root_entity_id: Optional[str] = None,
    depth: int = 2,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    # Aggregate evidence from findings + subgraph
    if root_entity_id:
        subgraph = investigation_subgraph(graph_repo, dataset, root_entity_id, depth=depth, case_id=case_id)
        snapshot_entities = {e.get("entity_id"): (e.get("entity_type", "Unknown"), e) for e in subgraph["entities"] if e.get("entity_id")}
        findings = generate_findings(case_id, root_entity_id, subgraph, [], snapshot_entities, subgraph["relationships"])
        # Collect evidence from findings
        evidence = []
        for f in findings:
            evidence.extend(f.get("evidence", []))
        # Deduplicate by evidence_id
        seen = set()
        deduped = []
        for ev in evidence:
            eid = ev.get("evidence_id")
            if eid not in seen:
                seen.add(eid)
                deduped.append(ev)
        return [InvestigationEvidenceOut(**e) for e in sorted(deduped, key=lambda x: x.get("evidence_id", ""))[:50]]
    else:
        # Global evidence from full graph
        entities_snap, rels_snap = graph_repo.export_snapshot()
        findings = generate_findings(case_id, None, {"entities": [], "relationships": rels_snap}, [], entities_snap, rels_snap)
        evidence = []
        for f in findings:
            evidence.extend(f.get("evidence", []))
        seen = set()
        deduped = []
        for ev in evidence:
            eid = ev.get("evidence_id")
            if eid not in seen:
                seen.add(eid)
                deduped.append(ev)
        return [InvestigationEvidenceOut(**e) for e in sorted(deduped, key=lambda x: x.get("evidence_id", ""))[:50]]


@router.post("/investigations/snapshot", response_model=InvestigationSnapshotResponse, tags=["investigations"])
async def post_investigation_snapshot(
    request: InvestigationSnapshotRequest,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = investigation_snapshot(
            graph_repo, dataset, request.case_id, request.root_entity_id, depth=request.depth,
            entity_types=request.entity_types, relationship_types=request.relationship_types,
            include_findings=request.include_findings, include_paths=request.include_paths, max_nodes=request.max_nodes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return InvestigationSnapshotResponse(**result)


@router.get("/investigations/snapshot", response_model=InvestigationSnapshotResponse, tags=["investigations"])
async def get_investigation_snapshot(
    case_id: Optional[str] = None,
    root_entity_id: str = "",
    depth: int = 2,
    entity_types: Optional[str] = None,
    relationship_types: Optional[str] = None,
    include_findings: bool = True,
    include_paths: bool = True,
    max_nodes: int = 200,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    if not root_entity_id:
        raise HTTPException(status_code=400, detail="root_entity_id is required")
    ent_filter = [s.strip() for s in entity_types.split(",") if s.strip()] if entity_types else None
    rel_filter = [s.strip() for s in relationship_types.split(",") if s.strip()] if relationship_types else None
    try:
        result = investigation_snapshot(
            graph_repo, dataset, case_id, root_entity_id, depth=depth,
            entity_types=ent_filter, relationship_types=rel_filter,
            include_findings=include_findings, include_paths=include_paths, max_nodes=max_nodes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return InvestigationSnapshotResponse(**result)


# ---------------------------------------------------------------------------
# Explainability & Audit — Milestone 9A
# ---------------------------------------------------------------------------

from app.schemas import AuditEventOut, AuditQueryResponse, ExplanationOut
from app.services import audit as audit_service
from app.services.explainability import (
    explain_bridge,
    explain_centrality,
    explain_chain,
    explain_community,
    explain_entity,
    explain_finding,
    explain_indicator,
    explain_strength,
    explain_temporal,
)


@router.get("/explainability/findings/{finding_id}", response_model=ExplanationOut, tags=["explainability"])
async def explain_finding_endpoint(
    finding_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = explain_finding(graph_repo, dataset, finding_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Explainability failed: {exc}")
    audit_service.record_event(
        event_type="explainability_requested",
        analysis_type="finding",
        object_id=finding_id,
        parameters={"finding_id": finding_id},
        status="completed",
    )
    return ExplanationOut(**result)


@router.get("/explainability/entities/{entity_id}", response_model=ExplanationOut, tags=["explainability"])
async def explain_entity_endpoint(
    entity_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = explain_entity(graph_repo, dataset, entity_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(
        event_type="explainability_requested",
        analysis_type="entity",
        entity_id=entity_id,
        object_id=entity_id,
        parameters={"entity_id": entity_id},
        status="completed",
    )
    return ExplanationOut(**result)


@router.get("/explainability/centrality/{entity_id}", response_model=ExplanationOut, tags=["explainability"])
async def explain_centrality_path(
    entity_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = explain_centrality(graph_repo, dataset, entity_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(event_type="explainability_requested", analysis_type="centrality", entity_id=entity_id, parameters={"entity_id": entity_id}, status="completed")
    return ExplanationOut(**result)


@router.get("/explainability/centrality", response_model=ExplanationOut, tags=["explainability"])
async def explain_centrality_query(
    entity_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = explain_centrality(graph_repo, dataset, entity_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(event_type="explainability_requested", analysis_type="centrality", entity_id=entity_id, parameters={"entity_id": entity_id}, status="completed")
    return ExplanationOut(**result)


@router.get("/explainability/communities", response_model=ExplanationOut, tags=["explainability"])
async def explain_communities_endpoint(
    entity_id: Optional[str] = None,
    case_id: Optional[str] = None,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = explain_community(graph_repo, dataset, entity_id=entity_id, case_id=case_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(event_type="explainability_requested", analysis_type="community", entity_id=entity_id, case_id=case_id, parameters={"entity_id": entity_id, "case_id": case_id}, status="completed")
    return ExplanationOut(**result)


@router.get("/explainability/communities/{entity_id}", response_model=ExplanationOut, tags=["explainability"])
async def explain_community_entity(
    entity_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = explain_community(graph_repo, dataset, entity_id=entity_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(event_type="explainability_requested", analysis_type="community", entity_id=entity_id, parameters={"entity_id": entity_id}, status="completed")
    return ExplanationOut(**result)


@router.get("/explainability/bridges/{entity_id}", response_model=ExplanationOut, tags=["explainability"])
async def explain_bridge_endpoint(
    entity_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = explain_bridge(graph_repo, dataset, entity_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(event_type="explainability_requested", analysis_type="bridge", entity_id=entity_id, parameters={"entity_id": entity_id}, status="completed")
    return ExplanationOut(**result)


@router.get("/explainability/temporal", response_model=ExplanationOut, tags=["explainability"])
async def explain_temporal_endpoint(
    entity_id: Optional[str] = None,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = explain_temporal(graph_repo, dataset, entity_id=entity_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(event_type="explainability_requested", analysis_type="temporal", entity_id=entity_id, parameters={"entity_id": entity_id}, status="completed")
    return ExplanationOut(**result)


@router.get("/explainability/transaction-chains", response_model=ExplanationOut, tags=["explainability"])
async def explain_chains_endpoint(
    chain_id: Optional[str] = None,
    account_id: Optional[str] = None,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = explain_chain(graph_repo, dataset, chain_id=chain_id, account_id=account_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(event_type="explainability_requested", analysis_type="transaction_chain", parameters={"chain_id": chain_id, "account_id": account_id}, status="completed")
    return ExplanationOut(**result)


@router.get("/explainability/indicators/{indicator_id}", response_model=ExplanationOut, tags=["explainability"])
async def explain_indicator_endpoint(
    indicator_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = explain_indicator(graph_repo, dataset, indicator_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(event_type="explainability_requested", analysis_type="indicator", object_id=indicator_id, parameters={"indicator_id": indicator_id}, status="completed")
    return ExplanationOut(**result)


@router.get("/explainability/relationship-strength/{relationship_id}", response_model=ExplanationOut, tags=["explainability"])
async def explain_strength_endpoint(
    relationship_id: str,
    graph_repo: GraphRepository = Depends(get_graph_repo),
    dataset: Dict[str, Any] = Depends(get_dataset),
):
    try:
        result = explain_strength(graph_repo, dataset, relationship_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_service.record_event(event_type="explainability_requested", analysis_type="relationship_strength", object_id=relationship_id, parameters={"relationship_id": relationship_id}, status="completed")
    return ExplanationOut(**result)


@router.get("/audit/events", response_model=AuditQueryResponse, tags=["audit"])
async def query_audit_events(
    case_id: Optional[str] = None,
    analysis_type: Optional[str] = None,
    event_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    root_entity_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    try:
        events = audit_service.query_events(
            case_id=case_id,
            analysis_type=analysis_type,
            event_type=event_type,
            entity_id=entity_id,
            root_entity_id=root_entity_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    total = audit_service.count_events()
    return AuditQueryResponse(events=[AuditEventOut(**e) for e in events], count=len(events), total=total, limit=limit, offset=offset)


@router.post("/audit/events/clear", tags=["audit"])
async def clear_audit_events():
    audit_service.clear_events()
    return {"status": "cleared", "count": 0}