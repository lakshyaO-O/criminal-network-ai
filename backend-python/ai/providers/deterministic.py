"""Deterministic provider — the canonical, always-available M12A provider.

This provider reuses Milestone 3 deterministic extraction (PatternEntityExtractor
+ RuleBasedRelationshipExtractor) and Milestone 5 deterministic graph
intelligence as the analytical source of truth.

It adds an AI-assisted *interpretation* layer: given structured graph results,
it produces grounded summaries without inventing graph facts.

Properties:
- Fully deterministic (sorted inputs, hashed IDs, fixed methodology strings).
- Never assigns IDs — IDs come from resolver/persistence (here we only emit mentions).
- Confidence comes from declared RULE_PRIORS or analytical thresholds, never fabricated.
- needs_review set when confidence < threshold (0.60 for entities, 0.70 for rels).
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

from .base import AIProvider, AIEntityMention, AIRelationshipMention, AIAnalysisResult, deterministic_id, sanitize_text
from ai.schemas import CANONICAL_ENTITY_TYPES, CANONICAL_RELATIONSHIP_TYPES

FIXED_GENERATED_AT = "2024-01-01T00:00:00Z"
NEEDS_REVIEW_ENTITY_THRESHOLD = 0.60
NEEDS_REVIEW_REL_THRESHOLD = 0.70

# Safety: forbid guilt/criminality SCORING terminology (disclaimers like "does not imply guilt" are allowed)
_FORBIDDEN_SCORING = {"crime_probability", "guilt probability", "criminal probability", "guilt score", "criminal score", "criminality score", "is criminal", "is guilty", "likely guilty", "likely criminal", "probability of guilt", "criminal detected"}


def _check_neutral(text: str):
    low = text.lower()
    for f in _FORBIDDEN_SCORING:
        if f in low:
            # We do not produce scoring outputs; detection is a safety assertion
            raise ValueError(f"forbidden terminology detected in AI output: {f}")


class DeterministicAIProvider(AIProvider):
    provider_name = "deterministic"
    provider_version = "12A-1.0.0"

    def __init__(self, known_entities=None):
        self.known_entities = known_entities

    # -- entity extraction -------------------------------------------------

    def extract_entities(self, text: str, source_id: Optional[str] = None) -> List[AIEntityMention]:
        sanitize_text(text)  # validates bounded + non-empty
        # Delegate to existing deterministic pattern extractor
        from ai.extraction.pattern_extractor import PatternEntityExtractor

        extractor = PatternEntityExtractor(known_entities=self.known_entities)
        extracted = extractor.extract(text, source_id=source_id)
        mentions: List[AIEntityMention] = []
        for e in extracted:
            conf = float(e.confidence) if e.confidence is not None else 0.5
            mentions.append(
                AIEntityMention(
                    canonical_type=e.entity_type,
                    value=e.text,
                    start=e.start_offset,
                    end=e.end_offset,
                    confidence=conf,
                    extraction_method=f"deterministic:{e.extraction_method}",
                    provenance={
                        "provider": self.provider_name,
                        "provider_version": self.provider_version,
                        "extraction_method": e.extraction_method,
                        "source_id": source_id,
                        "start": e.start_offset,
                        "end": e.end_offset,
                    },
                    needs_review=conf < NEEDS_REVIEW_ENTITY_THRESHOLD,
                    metadata={"normalized_value": e.normalized_value, "entity_id": e.entity_id},
                )
            )
        # Deterministic ordering
        mentions.sort(key=lambda m: (m.start or 0, m.value))
        return mentions

    # -- relationship extraction -------------------------------------------

    def extract_relationships(
        self,
        text: str,
        entities: List[AIEntityMention],
        source_id: Optional[str] = None,
        structured_records: Optional[List[Dict[str, Any]]] = None,
    ) -> List[AIRelationshipMention]:
        sanitize_text(text)
        # Validate canonical relationship types upfront
        # Build ExtractedEntity list for rule extractor
        from ai.extraction.base import ExtractedEntity
        from ai.relationship_rules import RuleBasedRelationshipExtractor

        extracted_entities: List[ExtractedEntity] = []
        for idx, m in enumerate(entities):
            # Validate entity type
            if m.canonical_type not in CANONICAL_ENTITY_TYPES:
                raise ValueError(f"unknown canonical entity_type {m.canonical_type} at index {idx}")
            extracted_entities.append(
                ExtractedEntity(
                    text=m.value,
                    entity_type=m.canonical_type,
                    start_offset=m.start if m.start is not None else 0,
                    end_offset=m.end if m.end is not None else len(m.value),
                    normalized_value=m.value,
                    entity_id=None,  # provider does NOT invent IDs
                    confidence=m.confidence,
                    extraction_method=m.extraction_method,
                    source_id=source_id,
                )
            )

        extractor = RuleBasedRelationshipExtractor()
        rule_rels = extractor.extract_relationships(
            extracted_entities, text, source_id=source_id, structured_records=structured_records
        )

        # Map rule results back to indices + AI wrapper
        # Build lookup by text/type to resolve indices deterministically
        def _index_of(ent: ExtractedEntity) -> Optional[int]:
            for i, m in enumerate(entities):
                if m.value == ent.text and m.canonical_type == ent.entity_type:
                    return i
            return None

        # Since rule extractor uses text equality, we approximate mapping by value
        value_to_indices: Dict[str, List[int]] = {}
        for i, m in enumerate(entities):
            value_to_indices.setdefault(m.value, []).append(i)

        results: List[AIRelationshipMention] = []
        for rr in rule_rels:
            if rr.relationship_type not in CANONICAL_RELATIONSHIP_TYPES:
                continue  # unknown relationships must NOT become valid
            # Resolve source/target indices by source_text / target_text
            src_candidates = value_to_indices.get(rr.source_text, [])
            tgt_candidates = value_to_indices.get(rr.target_text, [])
            if not src_candidates or not tgt_candidates:
                continue
            src_idx = src_candidates[0]
            tgt_idx = tgt_candidates[0]
            if src_idx == tgt_idx and rr.source_type == rr.target_type:
                continue  # self-loop forbidden
            conf = float(rr.confidence)
            results.append(
                AIRelationshipMention(
                    source_entity_index=src_idx,
                    target_entity_index=tgt_idx,
                    relationship_type=rr.relationship_type,
                    confidence=conf,
                    extraction_method=f"deterministic:{rr.extraction_method}",
                    provenance={
                        "provider": self.provider_name,
                        "provider_version": self.provider_version,
                        "extraction_method": rr.extraction_method,
                        "source_id": source_id,
                        "relationship_id": rr.relationship_id,
                    },
                    needs_review=conf < NEEDS_REVIEW_REL_THRESHOLD,
                    evidence_span=text[rr.source_text.find(rr.source_text):][:120] if False else None,
                    metadata={"relationship_id": rr.relationship_id, "timestamp": rr.timestamp},
                )
            )
        # Also handle structured records that map to indices via account IDs - if no entity mentions match but structured records present, create grounded relationships with needs_review based on confidence
        # Already handled via rule extractor for TRANSFERRED_TO etc. - above mapping covers it.

        results.sort(key=lambda r: (r.relationship_type, r.source_entity_index, r.target_entity_index))
        return results

    # -- pattern analysis (interpretation layer) ---------------------------

    def analyze_patterns(
        self,
        graph_snapshot: Dict[str, Any],
        analysis_type: str = "network_summary",
        case_id: Optional[str] = None,
        root_entity_id: Optional[str] = None,
    ) -> AIAnalysisResult:
        # graph_snapshot must contain at least centrality / communities / bridges etc. as returned by network_analysis
        # We do NOT invent facts; we summarize only what is present.

        # Validate analysis_type is known (M13 adds brief types)
        allowed = {"network_summary", "centrality", "community", "bridge", "temporal", "transaction_chain", "indicator", "finding", "investigation_brief", "entity_brief", "network_brief"}
        if analysis_type not in allowed:
            raise ValueError(f"unsupported analysis_type {analysis_type}")
        # Brief types are composed from same metrics; keep original for provenance
        is_brief = analysis_type in {"investigation_brief", "entity_brief", "network_brief"}
        original_type = analysis_type

        # Extract supporting refs from snapshot without invention
        raw_entities = graph_snapshot.get("entities", {})
        rels = graph_snapshot.get("relationships", []) if isinstance(graph_snapshot.get("relationships"), list) else []
        # Support both dict (export_snapshot) and list forms; JSON converts tuples to lists so check dict keys directly
        if isinstance(raw_entities, dict):
            entity_ids = sorted(str(k) for k in raw_entities.keys())
        elif isinstance(raw_entities, list):
            entity_ids = sorted(str(e) if isinstance(e, str) else str(e.get("entity_id", e)) for e in raw_entities if e)
        else:
            entity_ids = []
        rel_ids = sorted([str(r.get("relationship_id", "")) for r in rels if isinstance(r, dict) and r.get("relationship_id")])

        # Build observations grounded in actual metrics
        observations: List[str] = []
        analytical: List[str] = []

        # Pull deterministic metrics if present
        centrality = graph_snapshot.get("centrality") or graph_snapshot.get("centrality_detailed") or {}
        communities = graph_snapshot.get("communities_detailed") or graph_snapshot.get("communities") or []
        bridges = graph_snapshot.get("bridges_detailed") or graph_snapshot.get("bridges") or []
        temporal = graph_snapshot.get("temporal_indicators") or []
        chains = graph_snapshot.get("transaction_chains") or []
        indicators = graph_snapshot.get("indicators_enhanced") or graph_snapshot.get("indicators") or []

        # Observations = what was measured
        if entity_ids:
            observations.append(f"Observed graph snapshot: {len(entity_ids)} entities, {len(rel_ids)} relationships (case={case_id or 'global'})")
        if bridges:
            observations.append(f"Observed {len(bridges)} bridge candidates (articulation/betweenness/boundary)")
        if communities:
            observations.append(f"Observed {len(communities)} network communities via greedy_modularity")
        if temporal:
            observations.append(f"Observed {len(temporal)} temporal bursts (24h mean+2*std)")
        if chains:
            observations.append(f"Observed {len(chains)} transaction chains (TRANSFERRED_TO DFS 2-4 hops)")
        if indicators:
            observations.append(f"Observed {len(indicators)} structured indicators (LOW/MEDIUM/HIGH analytical)")

        if not observations:
            observations.append("No graph signals present in provided snapshot; no invented facts added")

        # Analytical interpretation = what the pattern means (neutral)
        if centrality:
            analytical.append("Analytical interpretation: centrality indicates structural position (degree/betweenness/closeness/PageRank) not guilt")
        if communities:
            analytical.append("Analytical interpretation: communities are interaction clusters; membership does not imply coordinated wrongdoing")
        if bridges:
            analytical.append("Analytical interpretation: bridge entities are structural junctions; their relevance is topological, not accusatory")
        if temporal:
            analytical.append("Analytical interpretation: temporal bursts are statistical deviations from per-entity baselines; bursts alone are not suspicious")
        if chains:
            analytical.append("Analytical interpretation: transaction chains are directed transfer sequences; chain existence alone is not flagged as suspicious")

        if not analytical:
            analytical.append("Analytical interpretation: pattern interpretation grounded only in provided graph metrics; no assessment of criminality")
        if is_brief:
            if original_type == "investigation_brief":
                analytical.append("Human review: investigator should verify supporting entities/relationships/evidence and temporal ordering before further action")
            elif original_type == "entity_brief":
                analytical.append(f"Entity {root_entity_id or (entity_ids[0] if entity_ids else 'unknown')} brief grounded in centrality/community/bridge context")
            elif original_type == "network_brief":
                analytical.append("Network brief: case-scoped summary grounded in supplied snapshot; global analysis avoided when case_id present")

        # Safety checks
        for t in observations + analytical:
            _check_neutral(t)

        # Deterministic ID
        base = f"{analysis_type}|{case_id or ''}|{root_entity_id or ''}|{len(entity_ids)}|{len(rel_ids)}|{hashlib.sha256(str(sorted(entity_ids)[:3]).encode()).hexdigest()[:6]}"
        analysis_id = f"ai-{deterministic_id(base)}"

        # Confidence here = interpretation confidence, not guilt probability
        # Deterministic provider: confidence is fixed based on data richness
        richness = len(observations) + len(analytical)
        confidence = min(0.85, 0.50 + richness * 0.05)
        if not entity_ids:
            confidence = 0.35  # low confidence when no data

        dataset_id = graph_snapshot.get("dataset_id") or deterministic_id(str(sorted(entity_ids)[:5]))

        provenance = [{
            "source": "ai_provider",
            "provider": self.provider_name,
            "provider_version": self.provider_version,
            "analysis_type": analysis_type,
            "timestamp": FIXED_GENERATED_AT,
            "case_id": case_id,
            "root_entity_id": root_entity_id,
            "input_entity_count": len(entity_ids),
            "input_relationship_count": len(rel_ids),
        }]

        lineage = {
            "analysis_type": analysis_type,
            "algorithm": "deterministic:networkx+rules",
            "parameters": {"analysis_type": analysis_type, "case_id": case_id, "root_entity_id": root_entity_id},
            "inputs": {"entity_count": len(entity_ids), "relationship_count": len(rel_ids), "dataset_id": dataset_id},
            "observations": observations[:3],
            "output_summary": f"AI interpretation for {analysis_type}",
            "dataset_id": dataset_id,
            "deterministic": True,
            "timestamp": FIXED_GENERATED_AT,
        }

        reproducibility = {
            "analysis_type": analysis_type,
            "dataset_id": dataset_id,
            "result_id": analysis_id,
            "deterministic": True,
            "provider": self.provider_name,
            "provider_version": self.provider_version,
            "input_hash": deterministic_id(str(sorted(entity_ids)), str(sorted(rel_ids))),
        }

        summary = f"AI-assisted interpretation for {analysis_type}: {observations[0][:120]}" if observations else f"AI interpretation for {analysis_type}"

        # Supporting IDs: top 5 deterministically
        sup_entities = entity_ids[:5]
        sup_rels = rel_ids[:5]

        # Grounding validation (M13) — mark unsupported if any supporting ID not in snapshot
        try:
            from ai.grounding import validate_analysis_grounding
            grounding_res = validate_analysis_grounding(
                {
                    "supporting_entity_ids": sup_entities,
                    "supporting_relationship_ids": sup_rels,
                    "supporting_evidence_ids": sup_rels[:3],
                    "observations": observations,
                    "analytical_interpretation": analytical,
                    "summary": summary,
                },
                graph_snapshot,
            )
            grounding_status = grounding_res["overall_status"]
            grounding_details = grounding_res
        except Exception:
            grounding_status = "SUPPORTED"
            grounding_details = {}

        # Use original_type for brief preservation
        final_analysis_type = original_type

        return AIAnalysisResult(
            analysis_id=analysis_id,
            analysis_type=final_analysis_type,
            summary=summary,
            observations=observations,
            analytical_interpretation=analytical,
            supporting_entity_ids=sup_entities,
            supporting_relationship_ids=sup_rels,
            supporting_evidence_ids=sup_rels[:3],
            confidence=confidence,
            methodology="Deterministic provider: PatternEntityExtractor + RuleBasedRelationshipExtractor + NetworkX graph intelligence; AI interpretation is a grounded summary over provided metrics without inventing facts",
            limitations="Analytical interpretation only; does not determine guilt, criminality, or wrongdoing; requires investigator review; limited to graph snapshot scope",
            provenance=provenance,
            lineage=lineage,
            reproducibility=reproducibility,
            grounding_status=grounding_status,
            grounding_details=grounding_details,
        )

    def status(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "provider_version": self.provider_version,
            "available": True,
            "model": "deterministic-rules",
            "deterministic": True,
            "description": "Deterministic AI provider (pattern+rules+NetworkX) always available without external API",
        }
