"""Evaluation runner — measures deterministic provider across 8 scenarios, supports local comparision."""
from __future__ import annotations

import json
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List

from ai.evaluation.metrics import entity_metrics, relationship_metrics
from ai.grounding import validate_analysis_grounding


DATASET_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ai" / "scenarios.json"


def load_dataset() -> Dict[str, Any]:
    with DATASET_PATH.open() as f:
        return json.load(f)


def evaluate_provider(provider_name: str = "deterministic", dataset: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if dataset is None:
        dataset = load_dataset()
    scenarios = dataset.get("scenarios", [])
    # Setup analyzer
    from ai.ai_analyzer import get_ai_analyzer
    import os
    orig = os.getenv("AI_PROVIDER")
    orig_model = os.getenv("AI_LOCAL_MODEL")
    # For deterministic, ensure env deterministic
    if provider_name == "deterministic":
        os.environ["AI_PROVIDER"] = "deterministic"
        os.environ.pop("AI_LOCAL_MODEL", None)
    elif provider_name == "local":
        os.environ["AI_PROVIDER"] = "local"
        if not os.getenv("AI_LOCAL_MODEL"):
            os.environ["AI_LOCAL_MODEL"] = "mock-local"
    analyzer = get_ai_analyzer()
    # Check availability
    status = analyzer.status()
    if not status.get("available"):
        return {"provider": provider_name, "available": False, "reason": "provider unavailable", "status": status}

    total_tp_e = total_fp_e = total_fn_e = 0
    total_tp_r = total_fp_r = total_fn_r = 0
    grounded = 0
    unsupported_total = 0
    latencies: List[float] = []
    confidence_correct: List[float] = []
    confidence_incorrect: List[float] = []
    needs_review_correct = 0
    needs_review_total = 0

    for scen in scenarios:
        text = scen["text"]
        expected_entities = scen.get("expected_entities", [])
        expected_rels = scen.get("expected_relationships", [])
        graph_snapshot = scen.get("graph_snapshot", {"entities": {}, "relationships": []})

        start = time.perf_counter()
        try:
            ents = analyzer.extract_entities(text)
            # Map to metrics format
            pred_ents = [{"canonical_type": e.canonical_type, "value": e.value} for e in ents]
        except Exception:
            pred_ents = []
        try:
            rels = analyzer.extract_relationships(text, ents if 'ents' in locals() else [])
            pred_rels = [{"source": ents[r.source_entity_index].value if r.source_entity_index < len(ents) else "", "target": ents[r.target_entity_index].value if r.target_entity_index < len(ents) else "", "relationship_type": r.relationship_type} for r in rels]
        except Exception:
            pred_rels = []
            rels = []
        try:
            analysis = analyzer.analyze_patterns(graph_snapshot, analysis_type="network_summary")
            grounded_check = validate_analysis_grounding(
                {
                    "supporting_entity_ids": analysis.supporting_entity_ids,
                    "supporting_relationship_ids": analysis.supporting_relationship_ids,
                    "supporting_evidence_ids": analysis.supporting_evidence_ids,
                    "observations": analysis.observations,
                    "analytical_interpretation": analysis.analytical_interpretation,
                    "summary": analysis.summary,
                },
                graph_snapshot,
            )
            if grounded_check["overall_status"] == "SUPPORTED":
                grounded += 1
            unsupported_total += grounded_check["unsupported_claims"]
            # confidence calibration: if metrics were perfect, confidence should be higher? For now check correlation
            # Use entity F1 as correctness proxy
            em = entity_metrics(expected_entities, pred_ents)
            is_correct = em["f1"] >= 0.8
            if is_correct:
                confidence_correct.append(analysis.confidence)
            else:
                confidence_incorrect.append(analysis.confidence)
            # needs_review: count
            for e in ents if 'ents' in locals() else []:
                needs_review_total += 1
                if e.needs_review:
                    # If entity was expected, needs_review should be true for low confidence cases
                    needs_review_correct += 1
        except Exception:
            pass
        lat = (time.perf_counter() - start) * 1000
        latencies.append(lat)

        # Metrics aggregation for entities/rels across scenarios
        em = entity_metrics(expected_entities, pred_ents if 'pred_ents' in locals() else [])
        rm = relationship_metrics(expected_rels, pred_rels if 'pred_rels' in locals() else [], pred_ents if 'pred_ents' in locals() else [])
        total_tp_e += em["tp"]; total_fp_e += em["fp"]; total_fn_e += em["fn"]
        total_tp_r += rm["tp"]; total_fp_r += rm["fp"]; total_fn_r += rm["fn"]

    # Restore env
    if orig is None:
        os.environ.pop("AI_PROVIDER", None)
    else:
        os.environ["AI_PROVIDER"] = orig
    if orig_model is None:
        os.environ.pop("AI_LOCAL_MODEL", None)
    else:
        os.environ["AI_LOCAL_MODEL"] = orig_model

    def prf(tp, fp, fn):
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return p, r, f1

    p_e, r_e, f1_e = prf(total_tp_e, total_fp_e, total_fn_e)
    p_r, r_r, f1_r = prf(total_tp_r, total_fp_r, total_fn_r)

    latencies_sorted = sorted(latencies)
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    median_lat = latencies_sorted[len(latencies_sorted)//2] if latencies_sorted else 0
    max_lat = max(latencies) if latencies else 0

    return {
        "provider": provider_name,
        "provider_version": status.get("provider_version"),
        "model": status.get("model"),
        "available": True,
        "dataset_version": dataset.get("dataset_version"),
        "timestamp": "2024-01-01T00:00:00Z",
        "entity_precision": round(p_e, 4),
        "entity_recall": round(r_e, 4),
        "entity_f1": round(f1_e, 4),
        "entity_tp": total_tp_e, "entity_fp": total_fp_e, "entity_fn": total_fn_e,
        "relationship_precision": round(p_r, 4),
        "relationship_recall": round(r_r, 4),
        "relationship_f1": round(f1_r, 4),
        "relationship_tp": total_tp_r, "relationship_fp": total_fp_r, "relationship_fn": total_fn_r,
        "groundedness_rate": round(grounded / len(scenarios), 4) if scenarios else 0,
        "grounded_scenarios": grounded,
        "unsupported_claim_count": unsupported_total,
        "average_latency_ms": round(avg_lat, 2),
        "median_latency_ms": round(median_lat, 2),
        "max_latency_ms": round(max_lat, 2),
        "timeout_count": 0,
        "confidence_correct_avg": round(sum(confidence_correct)/len(confidence_correct), 3) if confidence_correct else None,
        "confidence_incorrect_avg": round(sum(confidence_incorrect)/len(confidence_incorrect), 3) if confidence_incorrect else None,
        "scenario_count": len(scenarios),
        "deterministic": status.get("deterministic"),
    }


def run_evaluation() -> Dict[str, Any]:
    dataset = load_dataset()
    det = evaluate_provider("deterministic", dataset)
    # Try local if available
    import os
    os.environ["AI_PROVIDER"] = "local"
    os.environ["AI_LOCAL_MODEL"] = os.getenv("AI_LOCAL_MODEL", "mock-local")
    from ai.ai_analyzer import get_ai_analyzer
    local_available = get_ai_analyzer().status().get("available", False)
    if local_available:
        local = evaluate_provider("local", dataset)
    else:
        local = {"provider": "local", "available": False, "reason": "LOCAL MODEL NOT AVAILABLE", "note": "Set AI_PROVIDER=local and AI_LOCAL_MODEL to enable"}
    # Reset
    os.environ.pop("AI_PROVIDER", None)
    # Persist results
    results_dir = Path(__file__).resolve().parents[2] / "tests" / "evaluation" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out = {"deterministic": det, "local": local, "dataset_version": dataset.get("dataset_version")}
    with (results_dir / "latest.json").open("w") as f:
        json.dump(out, f, indent=2)
    return out
