"""Automated validation of the canonical model and synthetic data.

Run from the repo root:
    python -m unittest discover -s tests -v

Checks (milestone requirements):
- IDs are unique and follow the canonical {prefix}-##### format
- relationships reference existing entities (no dangling refs)
- timestamps are valid ISO 8601
- confidence values are between 0 and 1
- provenance fields exist on every relationship
- synthetic data contains no accidental real PII (fictional markers only)
- generator is deterministic for a fixed seed
"""

from __future__ import annotations

import json
import os
import re
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.schemas import (  # noqa: E402
    CANONICAL_ENTITY_TYPES,
    CANONICAL_RELATIONSHIP_TYPES,
    ENTITY_ID_PREFIXES,
    RelationshipSchema,
    SchemaValidationError,
)
from ai.synthetic_data_generator import build_dataset  # noqa: E402

SEED = 42
DATASET = build_dataset(seed=SEED)

ID_RE = re.compile(r"^[a-z]+-\d{5}$")
FICTIONAL_PHONE_RE = re.compile(r"^\+91-(90|91|92|93|94)-\d{7}$")

TYPE_KEY = {
    "persons": "Person",
    "organizations": "Organization",
    "phone_numbers": "PhoneNumber",
    "vehicles": "Vehicle",
    "locations": "Location",
    "financial_accounts": "FinancialAccount",
    "transactions": "Transaction",
    "communications": "Communication",
    "cases": "Case",
    "firs": "FIR",
    "events": "Event",
    "evidence": "Evidence",
}


def _all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _all_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _all_strings(v)


def _iso_ok(text: str) -> bool:
    try:
        datetime.fromisoformat(str(text).replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


class TestEntityIDs(unittest.TestCase):
    def test_ids_are_unique_within_each_collection(self):
        for key, etype in TYPE_KEY.items():
            rows = DATASET[key]
            pk = f"{ENTITY_ID_PREFIXES[etype]}_id"
            self.assertIn(pk, rows[0], f"{key}: missing primary id '{pk}'")
            ids = [r[pk] for r in rows]
            self.assertEqual(len(ids), len(set(ids)),
                             f"duplicate ids in {key}")

    def test_ids_match_canonical_prefix_and_format(self):
        for key, etype in TYPE_KEY.items():
            prefix = ENTITY_ID_PREFIXES[etype]
            pk_field = f"{prefix}_id"
            for row in DATASET[key]:
                eid = row[pk_field]
                self.assertTrue(
                    ID_RE.match(eid), f"{key}: bad id format '{eid}'")
                self.assertTrue(
                    eid.startswith(prefix + "-"),
                    f"{key}: id '{eid}' lacks '{prefix}-' prefix")
                # entity_id mirrors <type>_id
                self.assertEqual(row["entity_id"], eid)
                self.assertEqual(row["entity_type"], etype)


class TestReferentialIntegrity(unittest.TestCase):
    def test_every_relationship_references_existing_entities(self):
        known = {}
        for key, etype in TYPE_KEY.items():
            prefix = ENTITY_ID_PREFIXES[etype]
            pk_field = f"{prefix}_id"
            for row in DATASET[key]:
                known[row[pk_field]] = etype
        for rel in DATASET["relationships"]:
            for role in ("source", "target"):
                rid, rtype = rel[f"{role}_id"], rel[f"{role}_type"]
                self.assertIn(rid, known,
                              f"dangling {role} '{rid}' in "
                              f"{rel['relationship_id']}")
                self.assertEqual(known[rid], rtype,
                                 f"type mismatch for {role} '{rid}'")

    def test_no_self_loops(self):
        for rel in DATASET["relationships"]:
            self.assertFalse(
                rel["source_id"] == rel["target_id"]
                and rel["source_type"] == rel["target_type"],
                f"self-loop in {rel['relationship_id']}")

    def test_internal_foreign_keys_resolve(self):
        case_ids = {r["case_id"] for r in DATASET["cases"]}
        person_ids = {r["person_id"] for r in DATASET["persons"]}
        location_ids = {r["location_id"] for r in DATASET["locations"]}
        account_ids = {r["account_id"] for r in DATASET["financial_accounts"]}
        for fir in DATASET["firs"]:
            self.assertIn(fir["case_id"], case_ids)
            if fir["filed_by"] is not None:
                self.assertIn(fir["filed_by"], person_ids)
        for ev in DATASET["events"]:
            if ev["location_id"] is not None:
                self.assertIn(ev["location_id"], location_ids)
        for e in DATASET["evidence"]:
            self.assertIn(e["case_id"], case_ids)
            if e["collected_by"] is not None:
                self.assertIn(e["collected_by"], person_ids)
        for tx in DATASET["transactions"]:
            self.assertIn(tx["from_account_id"], account_ids)
            self.assertIn(tx["to_account_id"], account_ids)


class TestProvenanceAndValues(unittest.TestCase):
    def test_relationship_types_are_canonical(self):
        for rel in DATASET["relationships"]:
            self.assertIn(rel["relationship_type"],
                          CANONICAL_RELATIONSHIP_TYPES)

    def test_confidence_between_0_and_1(self):
        for rel in DATASET["relationships"]:
            self.assertGreaterEqual(rel["confidence"], 0.0)
            self.assertLessEqual(rel["confidence"], 1.0)

    def test_provenance_fields_exist_on_every_relationship(self):
        required = ("relationship_id", "source_id", "source_type",
                    "target_id", "target_type", "confidence",
                    "extraction_method", "created_at")
        for rel in DATASET["relationships"]:
            for field_name in required:
                self.assertNotIn(rel.get(field_name), (None, ""),
                                 f"{rel['relationship_id']}: missing "
                                 f"'{field_name}'")
            self.assertTrue(ID_RE.match(rel["relationship_id"]))
            self.assertTrue(rel["relationship_id"].startswith("rel-"))

    def test_timestamps_are_valid_iso_8601(self):
        timestamp_fields = {
            "transactions": ("timestamp",),
            "communications": ("timestamp",),
            "cases": ("opened_at",),
            "firs": ("filed_at",),
            "events": ("timestamp",),
            "evidence": ("collected_at",),
        }
        for key, fields in timestamp_fields.items():
            for row in DATASET[key]:
                for f in fields:
                    if row.get(f) is not None:
                        self.assertTrue(_iso_ok(row[f]),
                                        f"{key}.{f} invalid: {row[f]}")
                        self.assertTrue(row[f].endswith("Z"),
                                        f"{key}.{f} must be UTC ('Z')")
        for rel in DATASET["relationships"]:
            self.assertTrue(_iso_ok(rel["created_at"]))
            if rel["timestamp"] is not None:
                self.assertTrue(_iso_ok(rel["timestamp"]))
        for key in ("persons",):
            for row in DATASET[key]:
                self.assertTrue(_iso_ok(row["date_of_birth"] + "T00:00:00Z"))

    def test_relationships_validate_against_schemas_module(self):
        for rel in DATASET["relationships"]:
            try:
                RelationshipSchema(**{
                    k: v for k, v in rel.items() if k != "metadata"
                }).validate()
            except SchemaValidationError as exc:
                self.fail(f"{rel['relationship_id']} invalid: {exc}")


class TestNoRealPII(unittest.TestCase):
    FICTIONAL_MARKERS = ("SYN-CASE", "SYN-FIR", "REG-FIC", "-FIC",
                         "FIC", "FICA")

    def test_phone_numbers_use_fictional_ranges_only(self):
        numbers = [p["number"] for p in DATASET["phone_numbers"]]
        self.assertTrue(numbers)
        for number in numbers:
            self.assertRegex(number, FICTIONAL_PHONE_RE,
                             f"phone '{number}' outside fictional range")

    def test_identifiers_carry_fictional_markers(self):
        for v in DATASET["vehicles"]:
            self.assertIn("-FIC", v["registration_number"])
            self.assertTrue(v["vin"].startswith("FIC"))
        for a in DATASET["financial_accounts"]:
            self.assertTrue(a["account_number"].startswith("FICA"))
        for c in DATASET["cases"]:
            self.assertTrue(c["case_number"].startswith("SYN-CASE"))
        for f in DATASET["firs"]:
            self.assertTrue(f["fir_number"].startswith("SYN-FIR"))
        for o in DATASET["organizations"]:
            self.assertTrue(o["registration_number"].startswith("REG-FIC"))

    def test_no_real_indian_mobile_prefixes_outside_fictional_set(self):
        # Real Indian mobiles look like +91-9876543210; the corpus must only
        # ever contain the reserved-style +91-9x-XXXXXXX range.
        for comm in DATASET["communications"]:
            for s in _all_strings(comm):
                self.assertNotRegex(s, r"\+91-[6789]\d-\d{8}",
                                    "possible real-format mobile leaked")

    def test_evidence_is_metadata_only(self):
        for e in DATASET["evidence"]:
            for s in _all_strings(e):
                self.assertNotIn("data:image", s.lower())
                self.assertNotIn("base64,", s.lower())

    def test_generation_config_records_seed_and_safety_notice(self):
        cfg = DATASET["generation_config"]
        self.assertEqual(cfg["seed"], SEED)
        self.assertIn("fictional", cfg["safety_notice"].lower())
        self.assertIn("patterns", cfg)

    def test_no_guilt_or_criminality_labels(self):
        forbidden = ("criminal_status", "guilt", "is_criminal", "convicted")
        for rows in DATASET.values():
            if isinstance(rows, dict):
                continue
            for row in rows:
                blob = json.dumps(row).lower()
                for word in forbidden:
                    self.assertNotIn(word, blob,
                                     f"forbidden label '{word}' found")


class TestDeterminism(unittest.TestCase):
    def test_same_seed_produces_identical_output(self):
        a = json.dumps(build_dataset(seed=SEED), sort_keys=True)
        b = json.dumps(build_dataset(seed=SEED), sort_keys=True)
        self.assertEqual(a, b)

    def test_different_seed_changes_output(self):
        a = json.dumps(build_dataset(seed=SEED), sort_keys=True)
        b = json.dumps(build_dataset(seed=SEED + 1), sort_keys=True)
        self.assertNotEqual(a, b)


class TestStructuralPatterns(unittest.TestCase):
    def test_expected_pattern_markers_present(self):
        patterns = DATASET["generation_config"]["patterns"]
        expected = {"direct_relationships", "indirect_relationships",
                    "communities", "bridge_nodes", "repeated_communications",
                    "transaction_chains", "temporal_activity",
                    "unusual_behavior_demo"}
        self.assertTrue(expected.issubset(set(patterns)))

    def test_repeated_communications_exist(self):
        pairs = [
            tuple(sorted((c["from_entity_id"], c["to_entity_id"])))
            for c in DATASET["communications"]
        ]
        most_common = max(pairs.count(p) for p in set(pairs))
        self.assertGreaterEqual(most_common, 3,
                                "expected repeated contact pairs")

    def test_demo_anomaly_transactions_flagged(self):
        flagged = [t for t in DATASET["transactions"]
                   if t.get("is_flagged_demo")]
        self.assertGreater(len(flagged), 0,
                           "expected demo anomaly transactions")


if __name__ == "__main__":
    unittest.main()
