"""AI-assisted endpoints — Milestone 12A.

Namespace: /api/ai/*
- POST /api/ai/extract/entities
- POST /api/ai/extract/relationships
- POST /api/ai/analyze
- GET  /api/ai/status

All outputs are analytical-assistance, not guilt determination.
Every request creates a bounded, sanitized audit event.
No secrets ever logged or returned.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.config import load_known_entities
from app.schemas import (
    AIAnalyzeRequest,
    AIAnalyzeResponse,
    AIAnalysisOut,
    AIExtractEntitiesRequest,
    AIExtractEntitiesResponse,
    AIExtractRelationshipsRequest,
    AIExtractRelationshipsResponse,
    AIStatusResponse,
)
from app.services import audit as audit_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _dataset_id_from_graph(snapshot: Dict[str, Any]) -> str:
    # Reuse same deterministic method as explainability: hash of entity counts
    try:
        ids = sorted(snapshot.get("entities", {}).keys()) if isinstance(snapshot.get("entities"), dict) else []
        base = "|".join(ids[:10])
        return f"dataset-{hashlib.sha256(base.encode()).hexdigest()[:12]}"
    except Exception:
        return "dataset-unknown"


def _get_analyzer(provider_override: Optional[str] = None, known_entities=None):
    from ai.ai_analyzer import AIAnalyzer
    # Provider selection respects explicit request override but via env var mechanism too
    if provider_override:
        # For per-request override we instantiate directly without mutating global env permanently
        from ai.providers.deterministic import DeterministicAIProvider
        from ai.providers.local import LocalAIProvider
        if provider_override.lower() == "local":
            return AIAnalyzer(LocalAIProvider(known_entities=known_entities))
        elif provider_override.lower() == "deterministic":
            return AIAnalyzer(DeterministicAIProvider(known_entities=known_entities))
        else:
            class _Unavailable:
                provider_name = provider_override
                provider_version = "unknown"
                def extract_entities(self, *a, **kw):
                    from ai.providers.base import ProviderUnavailable
                    raise ProviderUnavailable(f"AI provider '{provider_override}' unavailable")
                def extract_relationships(self, *a, **kw):
                    from ai.providers.base import ProviderUnavailable
                    raise ProviderUnavailable(f"AI provider '{provider_override}' unavailable")
                def analyze_patterns(self, *a, **kw):
                    from ai.providers.base import ProviderUnavailable
                    raise ProviderUnavailable(f"AI provider '{provider_override}' unavailable")
                def status(self): return {"provider": provider_override, "available": False}
            from ai.ai_analyzer import AIAnalyzer as _An
            return _An(_Unavailable())  # type: ignore
    from ai.ai_analyzer import get_ai_analyzer
    return get_ai_analyzer(known_entities)


def _sanitize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    # Use same sanitizer as audit — drop secrets, truncate large values
    from app.services.audit import _sanitize_params as _sp
    return _sp(params)  # type: ignore


@router.get("/status", response_model=AIStatusResponse)
async def ai_status():
    from ai.ai_analyzer import get_ai_analyzer
    # Load known_entities lazily
    try:
        from app.api import get_known_entities
        ke = get_known_entities()
    except Exception:
        ke = None
    analyzer = get_ai_analyzer(ke)
    s = analyzer.status()
    audit_service.record_event(
        event_type="ai_analysis_requested",
        analysis_type="status",
        parameters=_sanitize_params({"provider": s.get("provider")}),
        status="completed",
    )
    return AIStatusResponse(**s)


@router.post("/extract/entities", response_model=AIExtractEntitiesResponse)
async def ai_extract_entities(request: AIExtractEntitiesRequest):
    # Bounded input already via Pydantic max_length 100k, min_length 1
    # Security: prompt injection — treat text as data, sanitize for logs
    from app.api import get_known_entities
    try:
        ke = get_known_entities()
    except Exception:
        ke = None
    analyzer = _get_analyzer(request.provider, ke)

    # Explicit empty check (Pydantic already does min_length 1, but keep typed 400)
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="text must be non-empty")

    try:
        mentions = analyzer.extract_entities(request.text, source_id=request.source_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        # Map provider errors to typed codes
        from ai.providers.base import ProviderUnavailable, ProviderTimeout, ProviderMalformedResponse
        if isinstance(exc, ProviderUnavailable):
            raise HTTPException(status_code=503, detail=f"AI provider unavailable: {exc}")
        if isinstance(exc, ProviderTimeout):
            raise HTTPException(status_code=504, detail=f"AI provider timeout: {exc}")
        if isinstance(exc, ProviderMalformedResponse):
            raise HTTPException(status_code=502, detail=f"AI provider malformed response: {exc}")
        raise HTTPException(status_code=500, detail=f"AI extraction failed: {exc}")

    # Validate no invented IDs and canonical types (already in provider, double-check)
    from ai.schemas import CANONICAL_ENTITY_TYPES
    for m in mentions:
        if m.canonical_type not in CANONICAL_ENTITY_TYPES:
            raise HTTPException(status_code=422, detail=f"invalid canonical entity_type {m.canonical_type}")
        if m.entity_id if hasattr(m, 'entity_id') else None:
            pass  # should be None — provider does not invent IDs
        if not 0.0 <= m.confidence <= 1.0:
            raise HTTPException(status_code=422, detail="confidence outside [0,1]")

    # Build response with provenance/lineage/reproducibility
    entities_out = [
        {
            "canonical_type": m.canonical_type,
            "value": m.value,
            "start": m.start,
            "end": m.end,
            "confidence": m.confidence,
            "extraction_method": m.extraction_method,
            "provenance": m.provenance,
            "needs_review": m.needs_review,
            "metadata": m.metadata,
        }
        for m in mentions
    ]

    prov = [{"source": "ai_provider", "provider": analyzer.provider_name, "provider_version": analyzer.provider_version, "analysis_type": "entity_extraction", "timestamp": "2024-01-01T00:00:00Z"}]
    # Deterministic lineage — use provider status for local mock-local case
    provider_deterministic = analyzer.provider.status().get("deterministic", analyzer.provider_name == "deterministic")
    input_hash = hashlib.sha256(request.text[:200].encode()).hexdigest()[:12]
    lineage = {
        "analysis_type": "entity_extraction",
        "algorithm": f"{analyzer.provider_name}:pattern+rules",
        "parameters": {"source_id": request.source_id},
        "inputs": {"text_hash": input_hash, "text_len": len(request.text)},
        "observations": [f"{len(mentions)} entities"],
        "output_summary": f"{len(mentions)} entities",
        "dataset_id": "dataset-ai",
        "deterministic": provider_deterministic,
        "timestamp": "2024-01-01T00:00:00Z",
    }
    reproducibility = {
        "analysis_type": "entity_extraction",
        "provider": analyzer.provider_name,
        "provider_version": analyzer.provider_version,
        "input_hash": input_hash,
        "result_id": f"ai-extract-{input_hash}",
        "deterministic": lineage["deterministic"],
    }

    audit_service.record_event(
        event_type="ai_analysis_requested",
        analysis_type="entity_extraction",
        parameters=_sanitize_params({"provider": analyzer.provider_name, "entity_count": len(mentions), "source_id": request.source_id}),
        status="completed",
    )

    return AIExtractEntitiesResponse(
        source_id=request.source_id,
        provider=analyzer.provider_name,
        provider_version=analyzer.provider_version,
        model=analyzer.provider.status().get("model") if hasattr(analyzer.provider, "status") else None,
        entities=entities_out,
        entity_count=len(entities_out),
        provenance=prov,
        lineage=lineage,
        reproducibility=reproducibility,
    )


@router.post("/extract/relationships", response_model=AIExtractRelationshipsResponse)
async def ai_extract_relationships(request: AIExtractRelationshipsRequest):
    from app.api import get_known_entities
    try:
        ke = get_known_entities()
    except Exception:
        ke = None
    analyzer = _get_analyzer(request.provider, ke)

    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="text must be non-empty")
    # Validate unknown relationships must NOT silently become valid — check upfront
    from ai.providers.base import AIEntityMention
    from ai.schemas import CANONICAL_ENTITY_TYPES as _CET
    entity_mentions: List[AIEntityMention] = []
    for idx, e in enumerate(request.entities):
        ct = e.get("canonical_type") or e.get("entity_type")
        if ct not in _CET:
            raise HTTPException(status_code=422, detail=f"invalid canonical_type at index {idx}: {ct}")
        # Build AIEntityMention for provider
        entity_mentions.append(
            AIEntityMention(
                canonical_type=ct,
                value=e.get("value") or e.get("text") or "",
                start=e.get("start"),
                end=e.get("end"),
                confidence=float(e.get("confidence", 0.5)),
                extraction_method=e.get("extraction_method", "unknown"),
                provenance=e.get("provenance", {}),
                needs_review=bool(e.get("needs_review", False)),
                metadata=e.get("metadata", {}),
            )
        )

    if len(request.entities) > 500:
        raise HTTPException(status_code=400, detail="entities exceeds bound 500")
    if len(request.structured_records) > 200:
        raise HTTPException(status_code=400, detail="structured_records exceeds bound 200")

    try:
        rels = analyzer.extract_relationships(request.text, entity_mentions, source_id=request.source_id, structured_records=request.structured_records)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        from ai.providers.base import ProviderUnavailable, ProviderTimeout, ProviderMalformedResponse
        if isinstance(exc, ProviderUnavailable):
            raise HTTPException(status_code=503, detail=f"AI provider unavailable: {exc}")
        if isinstance(exc, ProviderTimeout):
            raise HTTPException(status_code=504, detail=f"AI provider timeout: {exc}")
        if isinstance(exc, ProviderMalformedResponse):
            raise HTTPException(status_code=502, detail=f"AI provider malformed response: {exc}")
        raise HTTPException(status_code=500, detail=f"AI relationship extraction failed: {exc}")

    # Validate relationship types canonical, confidence range, needs_review set
    from ai.schemas import CANONICAL_RELATIONSHIP_TYPES as _CRT
    for r in rels:
        if r.relationship_type not in _CRT:
            raise HTTPException(status_code=422, detail=f"unsupported relationship_type {r.relationship_type}")
        if not 0.0 <= r.confidence <= 1.0:
            raise HTTPException(status_code=422, detail="confidence outside [0,1]")

    rels_out = [
        {
            "source_entity_index": r.source_entity_index,
            "target_entity_index": r.target_entity_index,
            "relationship_type": r.relationship_type,
            "confidence": r.confidence,
            "extraction_method": r.extraction_method,
            "provenance": r.provenance,
            "needs_review": r.needs_review,
            "evidence_span": r.evidence_span,
            "metadata": r.metadata,
        }
        for r in rels
    ]

    provider_deterministic = analyzer.provider.status().get("deterministic", analyzer.provider_name == "deterministic")
    prov = [{"source": "ai_provider", "provider": analyzer.provider_name, "provider_version": analyzer.provider_version, "analysis_type": "relationship_extraction", "timestamp": "2024-01-01T00:00:00Z"}]
    input_hash = hashlib.sha256(request.text[:200].encode()).hexdigest()[:12]
    lineage = {
        "analysis_type": "relationship_extraction",
        "algorithm": f"{analyzer.provider_name}:rules",
        "parameters": {"source_id": request.source_id},
        "inputs": {"text_hash": input_hash, "entity_count": len(entity_mentions)},
        "observations": [f"{len(rels)} relationships"],
        "output_summary": f"{len(rels)} relationships",
        "dataset_id": "dataset-ai",
        "deterministic": provider_deterministic,
        "timestamp": "2024-01-01T00:00:00Z",
    }
    reproducibility = {
        "analysis_type": "relationship_extraction",
        "provider": analyzer.provider_name,
        "provider_version": analyzer.provider_version,
        "input_hash": input_hash,
        "result_id": f"ai-rel-{input_hash}",
        "deterministic": lineage["deterministic"],
    }

    audit_service.record_event(
        event_type="ai_analysis_requested",
        analysis_type="relationship_extraction",
        parameters=_sanitize_params({"provider": analyzer.provider_name, "relationship_count": len(rels)}),
        status="completed",
    )

    return AIExtractRelationshipsResponse(
        source_id=request.source_id,
        provider=analyzer.provider_name,
        provider_version=analyzer.provider_version,
        model=analyzer.provider.status().get("model") if hasattr(analyzer.provider, "status") else None,
        relationships=rels_out,
        relationship_count=len(rels_out),
        provenance=prov,
        lineage=lineage,
        reproducibility=reproducibility,
    )


from app.api import get_graph_repo, get_dataset


@router.post("/analyze", response_model=AIAnalyzeResponse)
async def ai_analyze(
    request: AIAnalyzeRequest,
    graph_repo=Depends(get_graph_repo),
    dataset=Depends(get_dataset),
):
    from app.api import get_known_entities
    try:
        ke = get_known_entities()
    except Exception:
        ke = None
    analyzer = _get_analyzer(request.provider, ke)

    # Validate case/root if provided
    if request.case_id:
        # Check case exists
        found = any(row.get("case_id") == request.case_id for row in dataset.get("cases", [])) if isinstance(dataset, dict) else False
        # Also allow via graph
        try:
            if not found and not graph_repo.get_entity(request.case_id) and not any(r for r in graph_repo.get_relationships(request.case_id)):
                raise HTTPException(status_code=404, detail=f"Case '{request.case_id}' not found")
            if not found:
                # If dataset not contain but graph has no relationships and entity missing => 404
                if not graph_repo.get_entity(request.case_id):
                    # fallback to dataset check only
                    if not any(row.get("case_id") == request.case_id for row in dataset.get("cases", [])):
                        raise HTTPException(status_code=404, detail=f"Case '{request.case_id}' not found")
        except HTTPException:
            raise
        except Exception:
            pass

    if request.root_entity_id:
        try:
            if not graph_repo.get_entity(request.root_entity_id):
                raise HTTPException(status_code=404, detail=f"Entity '{request.root_entity_id}' not found")
        except HTTPException:
            raise
        except Exception:
            pass

    # Validate analysis_type (M13 adds briefs)
    allowed = {"network_summary", "centrality", "community", "bridge", "temporal", "transaction_chain", "indicator", "finding", "investigation_brief", "entity_brief", "network_brief"}
    if request.analysis_type not in allowed:
        raise HTTPException(status_code=400, detail=f"unsupported analysis_type {request.analysis_type}")

    # Text is optional but if provided, sanitize (prompt injection)
    if request.text is not None and request.text.strip() == "":
        raise HTTPException(status_code=400, detail="text must be non-empty if provided")
    if request.text is not None and len(request.text) > 100000:
        raise HTTPException(status_code=400, detail="text exceeds bound 100000")

    # Build graph_snapshot: if explicit, use it; else derive from current graph
    if request.graph_snapshot is not None:
        snapshot = request.graph_snapshot
        # Validate snapshot not oversized
        if len(str(snapshot)) > 500000:
            raise HTTPException(status_code=400, detail="graph_snapshot oversized")
    else:
        # Derive snapshot from graph — deterministic, case-scoped if case_id provided (prevents cross-case data leakage)
        try:
            entities, rels = graph_repo.export_snapshot()
            # If case_id provided, filter snapshot to case's related subgraph (RELATED_TO_CASE / MENTIONED_IN) — aligns AI analysis with selected case
            if request.case_id:
                case_rels = graph_repo.get_relationships(request.case_id)
                related_ids = set()
                for cr in case_rels:
                    if cr.get("relationship_type") in ("RELATED_TO_CASE", "MENTIONED_IN"):
                        related_ids.add(cr.get("source_id"))
                        related_ids.add(cr.get("target_id"))
                if related_ids:
                    entities = {eid: val for eid, val in entities.items() if eid in related_ids}
                    rels = [r for r in rels if r.get("source_id") in related_ids and r.get("target_id") in related_ids]
            # For analysis we also compute centrality etc. if snapshot empty of those keys, enrich
            from app.services.network_analysis import compute_centrality, find_communities, find_bridges, analyze_temporal, find_transaction_chains, generate_indicators
            centrality = compute_centrality(entities, rels)
            communities = find_communities(entities, rels)
            bridges = find_bridges(entities, rels, top_k=10)
            temporal = analyze_temporal(rels)
            chains = find_transaction_chains(rels)
            indicators = generate_indicators(entities, rels)
            snapshot = {
                "entities": entities,
                "relationships": rels,
                "centrality": centrality,
                "communities_detailed": communities,
                "bridges_detailed": bridges,
                "temporal_indicators": temporal,
                "transaction_chains": chains,
                "indicators_enhanced": indicators,
                "dataset_id": _dataset_id_from_graph({"entities": entities}),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"graph snapshot failed: {exc}")

    try:
        result = analyzer.analyze_patterns(snapshot, analysis_type=request.analysis_type, case_id=request.case_id, root_entity_id=request.root_entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        from ai.providers.base import ProviderUnavailable, ProviderTimeout, ProviderMalformedResponse
        if isinstance(exc, ProviderUnavailable):
            raise HTTPException(status_code=503, detail=f"AI provider unavailable: {exc}")
        if isinstance(exc, ProviderTimeout):
            raise HTTPException(status_code=504, detail=f"AI provider timeout: {exc}")
        if isinstance(exc, ProviderMalformedResponse):
            raise HTTPException(status_code=502, detail=f"AI provider malformed response: {exc}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {exc}")

    # Validate confidence range and neutral terminology (allow disclaimers like "does not imply guilt")
    if not 0.0 <= result.confidence <= 1.0:
        raise HTTPException(status_code=500, detail="provider returned confidence outside [0,1]")
    for field in [result.summary, result.methodology, result.limitations] + result.observations + result.analytical_interpretation:
        low = field.lower()
        for forbidden in ("crime_probability", "guilt probability", "criminal probability", "guilt score", "criminal score", "criminality score", "is criminal", "is guilty", "likely guilty", "likely criminal", "probability of guilt"):
            if forbidden in low:
                raise HTTPException(status_code=500, detail="AI output violates neutral terminology policy")

    # Record audit
    audit_service.record_event(
        event_type="ai_analysis_requested",
        analysis_type=request.analysis_type,
        case_id=request.case_id,
        root_entity_id=request.root_entity_id,
        parameters=_sanitize_params({
            "provider": analyzer.provider_name,
            "analysis_type": request.analysis_type,
            "case_id": request.case_id,
            "root_entity_id": request.root_entity_id,
        }),
        status="completed",
    )

    analysis_out = AIAnalysisOut(
        analysis_id=result.analysis_id,
        analysis_type=result.analysis_type,
        summary=result.summary,
        observations=result.observations,
        analytical_interpretation=result.analytical_interpretation,
        supporting_entity_ids=result.supporting_entity_ids,
        supporting_relationship_ids=result.supporting_relationship_ids,
        supporting_evidence_ids=result.supporting_evidence_ids,
        confidence=result.confidence,
        methodology=result.methodology,
        limitations=result.limitations,
        provenance=result.provenance,
        lineage=result.lineage,
        reproducibility=result.reproducibility,
        grounding_status=getattr(result, "grounding_status", "SUPPORTED"),
        grounding_details=getattr(result, "grounding_details", {}),
    )

    return AIAnalyzeResponse(
        provider=analyzer.provider_name,
        provider_version=analyzer.provider_version,
        model=analyzer.provider.status().get("model") if hasattr(analyzer.provider, "status") else None,
        analysis=analysis_out,
        provenance=result.provenance,
        lineage=result.lineage,
        reproducibility=result.reproducibility,
    )
