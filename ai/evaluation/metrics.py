"""Metrics for M13 evaluation — entity/relationship precision/recall/F1, groundedness, latency, confidence calibration."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def compute_prf(tp: int, fp: int, fn: int) -> Dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def _entity_key(e: Dict[str, Any]) -> Tuple[str, str]:
    # canonical_type + value (normalized lower)
    return (str(e.get("canonical_type", e.get("entity_type", e.get("type", "")))).strip(), str(e.get("value", e.get("text", ""))).strip().lower())


def entity_metrics(expected: List[Dict[str, Any]], predicted: List[Dict[str, Any]]) -> Dict[str, Any]:
    exp_set = set(_entity_key(e) for e in expected)
    pred_set = set(_entity_key(e) for e in predicted)
    tp = len(exp_set & pred_set)
    fp = len(pred_set - exp_set)
    fn = len(exp_set - pred_set)
    res = compute_prf(tp, fp, fn)
    res["expected_count"] = len(exp_set)
    res["predicted_count"] = len(pred_set)
    return res


def _rel_key(r: Dict[str, Any]) -> Tuple[str, str, str]:
    # source value + target value + type (all lower)
    src = str(r.get("source", r.get("source_entity", r.get("src", "")))).strip().lower()
    tgt = str(r.get("target", r.get("target_entity", r.get("tgt", "")))).strip().lower()
    # For AIRelationshipMention style, source is index; we need to map via entities list — caller handles
    # For ground truth style: source/target are values
    typ = str(r.get("relationship_type", r.get("type", ""))).strip().upper()
    return (src, tgt, typ)


def relationship_metrics(expected: List[Dict[str, Any]], predicted: List[Dict[str, Any]], entity_list: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    # If predicted relationships use indices, resolve to values via entity_list
    def normalize_expected(lst: List[Dict]) -> set:
        s = set()
        for r in lst:
            src = str(r.get("source", "")).strip().lower()
            tgt = str(r.get("target", "")).strip().lower()
            typ = str(r.get("relationship_type", r.get("type", ""))).strip().upper()
            s.add((src, tgt, typ))
        return s

    def normalize_predicted(lst: List[Dict], ents: List[Dict] | None) -> set:
        s = set()
        for r in lst:
            # If indices present, map
            if "source_entity_index" in r and ents is not None:
                try:
                    src = str(ents[r["source_entity_index"]].get("value", "")).strip().lower()
                    tgt = str(ents[r["target_entity_index"]].get("value", "")).strip().lower()
                except:
                    src = str(r.get("source_entity_index"))
                    tgt = str(r.get("target_entity_index"))
            else:
                src = str(r.get("source", r.get("source_id", ""))).strip().lower()
                tgt = str(r.get("target", r.get("target_id", ""))).strip().lower()
            typ = str(r.get("relationship_type", r.get("type", ""))).strip().upper()
            s.add((src, tgt, typ))
        return s

    exp_set = normalize_expected(expected)
    pred_set = normalize_predicted(predicted, entity_list)
    tp = len(exp_set & pred_set)
    fp = len(pred_set - exp_set)
    fn = len(exp_set - pred_set)
    res = compute_prf(tp, fp, fn)
    res["expected_count"] = len(exp_set)
    res["predicted_count"] = len(pred_set)
    return res
