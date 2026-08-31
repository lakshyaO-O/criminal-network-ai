"""Grounding validator for M13 — verifies AI outputs refer to real supplied graph context.

Validates:
- Entity references exist in supplied graph
- Relationship references exist
- Evidence references exist when evidence context supplied
- Case membership when case_id supplied (related_ids via RELATED_TO_CASE/MENTIONED_IN)
- Numerical facts come from supplied structured data (counts, metrics)
- Temporal facts grounded in supplied timestamps

Returns flags: SUPPORTED vs NEEDS_REVIEW / unsupported.

Used by both backend (AIAnalysisResult post-processing) and evaluation framework.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set


def validate_entity_references(supporting_entity_ids: List[str], graph_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    entities = graph_snapshot.get("entities", {})
    if isinstance(entities, dict):
        valid_ids = set(str(k) for k in entities.keys())
    elif isinstance(entities, list):
        valid_ids = set(str(e.get("entity_id", e)) if isinstance(e, dict) else str(e) for e in entities)
    else:
        valid_ids = set()
    unsupported = [eid for eid in supporting_entity_ids if eid not in valid_ids]
    return {
        "valid": len(unsupported) == 0,
        "unsupported": unsupported,
        "status": "SUPPORTED" if not unsupported else "NEEDS_REVIEW",
    }


def validate_relationship_references(supporting_relationship_ids: List[str], graph_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    rels = graph_snapshot.get("relationships", [])
    valid_ids = set(str(r.get("relationship_id")) for r in rels if isinstance(r, dict) and r.get("relationship_id"))
    unsupported = [rid for rid in supporting_relationship_ids if rid not in valid_ids]
    return {
        "valid": len(unsupported) == 0,
        "unsupported": unsupported,
        "status": "SUPPORTED" if not unsupported else "NEEDS_REVIEW",
    }


def validate_evidence_references(supporting_evidence_ids: List[str], graph_snapshot: Dict[str, Any], evidence_context: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    if not supporting_evidence_ids:
        return {"valid": True, "unsupported": [], "status": "SUPPORTED"}
    # Evidence context may be supplied separately; if not, check relationships as evidence
    valid = set()
    if evidence_context:
        valid.update(str(e.get("evidence_id")) for e in evidence_context if isinstance(e, dict) and e.get("evidence_id"))
    # Fallback: treat relationship_ids as valid evidence
    rels = graph_snapshot.get("relationships", [])
    valid.update(str(r.get("relationship_id")) for r in rels if isinstance(r, dict) and r.get("relationship_id"))
    unsupported = [eid for eid in supporting_evidence_ids if eid not in valid]
    return {
        "valid": len(unsupported) == 0,
        "unsupported": unsupported,
        "status": "SUPPORTED" if not unsupported else "NEEDS_REVIEW",
    }


def validate_case_membership(supporting_ids: List[str], case_id: str | None, graph_snapshot: Dict[str, Any], dataset: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not case_id or not supporting_ids:
        return {"valid": True, "unsupported": [], "status": "SUPPORTED"}
    # Build related_ids for case (same logic as ai_router)
    related_ids: Set[str] = set()
    # Try to get case relationships from snapshot if present, else from graph_snapshot's relationships
    # Snapshot's relationships already filtered if case_id was supplied, so we check dataset if available
    if dataset and isinstance(dataset, dict):
        case_rels = []
        for rel in graph_snapshot.get("relationships", []):
            if rel.get("relationship_type") in ("RELATED_TO_CASE", "MENTIONED_IN"):
                if rel.get("source_id") == case_id or rel.get("target_id") == case_id:
                    related_ids.add(rel.get("source_id"))
                    related_ids.add(rel.get("target_id"))
        # Also from dataset cases
        if not related_ids:
            # If snapshot is already case-filtered, all ids are valid
            entities = graph_snapshot.get("entities", {})
            if isinstance(entities, dict):
                valid_case = set(str(k) for k in entities.keys())
            else:
                valid_case = set()
            unsupported = [i for i in supporting_ids if i not in valid_case and not i.startswith("rel-")]
            # For relationship ids, check separately
            rel_ids = set(str(r.get("relationship_id")) for r in graph_snapshot.get("relationships", []) if isinstance(r, dict))
            unsupported_rel = [i for i in supporting_ids if i.startswith("rel-") and i not in rel_ids]
            unsupported = unsupported + unsupported_rel
            return {"valid": len(unsupported) == 0, "unsupported": unsupported, "status": "SUPPORTED" if not unsupported else "NEEDS_REVIEW"}
        related_ids.add(case_id)
    else:
        related_ids.add(case_id)
        entities = graph_snapshot.get("entities", {})
        if isinstance(entities, dict):
            related_ids.update(str(k) for k in entities.keys())
    unsupported = [i for i in supporting_ids if i not in related_ids and not i.startswith("rel-")]
    # Also check rel ids
    rel_ids = set(str(r.get("relationship_id")) for r in graph_snapshot.get("relationships", []) if isinstance(r, dict))
    for rid in supporting_ids:
        if rid.startswith("rel-") and rid not in rel_ids:
            if rid not in unsupported:
                unsupported.append(rid)
    return {"valid": len(unsupported) == 0, "unsupported": unsupported, "status": "SUPPORTED" if not unsupported else "NEEDS_REVIEW"}


def validate_numerical_facts(text: str, graph_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Check that numbers like counts/metrics in AI output are grounded in snapshot's computed metrics."""
    # For now, ensure if text mentions a count like "302 entities" that it matches len(entities)
    import re
    entities = graph_snapshot.get("entities", {})
    if isinstance(entities, dict):
        entity_count = len(entities)
    elif isinstance(entities, list):
        entity_count = len(entities)
    else:
        entity_count = 0
    # Simple check: extract numbers preceding "entities"
    found = re.findall(r"(\d+)\s+entities", text)
    unsupported_numbers = []
    for num_str in found:
        try:
            num = int(num_str)
            if num != entity_count and entity_count != 0:
                unsupported_numbers.append(num_str)
        except:
            pass
    return {"valid": len(unsupported_numbers) == 0, "unsupported": unsupported_numbers, "status": "SUPPORTED" if not unsupported_numbers else "NEEDS_REVIEW"}


def validate_temporal_facts(text: str, graph_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure timestamps mentioned are in supplied relationships."""
    import re
    rels = graph_snapshot.get("relationships", [])
    timestamps = set(str(r.get("timestamp")) for r in rels if isinstance(r, dict) and r.get("timestamp"))
    # Extract ISO timestamps from text
    found = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text)
    unsupported = [t for t in found if t not in timestamps and timestamps]
    # If no timestamps in snapshot, don't flag
    if not timestamps:
        unsupported = []
    return {"valid": len(unsupported) == 0, "unsupported": unsupported, "status": "SUPPORTED" if not unsupported else "NEEDS_REVIEW"}


def validate_analysis_grounding(analysis_result: Dict[str, Any], graph_snapshot: Dict[str, Any], dataset: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Full grounding check for an AIAnalysisResult dict (or AIAnalysisOut)."""
    entity_check = validate_entity_references(analysis_result.get("supporting_entity_ids", []), graph_snapshot)
    rel_check = validate_relationship_references(analysis_result.get("supporting_relationship_ids", []), graph_snapshot)
    ev_check = validate_evidence_references(analysis_result.get("supporting_evidence_ids", []), graph_snapshot)
    case_check = validate_case_membership(
        analysis_result.get("supporting_entity_ids", []) + analysis_result.get("supporting_relationship_ids", []),
        analysis_result.get("case_id") or (analysis_result.get("provenance", [{}])[0].get("case_id") if analysis_result.get("provenance") else None),
        graph_snapshot,
        dataset,
    )
    # Combine observations + interpretation for numerical/temporal checks
    combined_text = " ".join(analysis_result.get("observations", []) + analysis_result.get("analytical_interpretation", []) + [analysis_result.get("summary", "")])
    num_check = validate_numerical_facts(combined_text, graph_snapshot)
    temporal_check = validate_temporal_facts(combined_text, graph_snapshot)

    overall_valid = all(c["valid"] for c in [entity_check, rel_check, ev_check, case_check, num_check, temporal_check])
    return {
        "overall_status": "SUPPORTED" if overall_valid else "NEEDS_REVIEW",
        "checks": {
            "entities": entity_check,
            "relationships": rel_check,
            "evidence": ev_check,
            "case_membership": case_check,
            "numerical": num_check,
            "temporal": temporal_check,
        },
        "unsupported_claims": sum(len(c["unsupported"]) for c in [entity_check, rel_check, ev_check, case_check, num_check, temporal_check]),
    }
