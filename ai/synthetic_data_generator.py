"""Deterministic synthetic data generator for SIH 26189.

Generates COMPLETELY FICTIONAL data for development and demonstration.
All names, phone numbers, organizations, locations, accounts, etc. are
fabricated. No real PII, no real case data, no real criminal records.

Design guarantees:
- Deterministic: same seed => byte-identical dataset (including created_at,
  which is derived from the seed rather than wall-clock time).
- Interconnected: demonstrates direct relationships, indirect relationships,
  communities, bridge nodes, repeated communications, transaction chains,
  temporal activity, and unusual behavior.
- Canonical: every entity carries entity_id/entity_type; every relationship
  carries full provenance per ai/schemas.RelationshipSchema.

SAFETY: This system is investigator-assistance only. Synthetic entities are
never labeled as criminals; cases use neutral investigative language.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .schemas import (
    CANONICAL_ENTITY_TYPES,
    CANONICAL_RELATIONSHIP_TYPES,
)

RANDOM_SEED = 42

# Fixed epoch so created_at fields are deterministic for a given seed.
# Derived from the seed itself: same seed -> same epoch -> identical bytes.
_GENESIS = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

ENTITY_TYPE_PERSON = "Person"
ENTITY_TYPE_ORGANIZATION = "Organization"
ENTITY_TYPE_PHONENUMBER = "PhoneNumber"
ENTITY_TYPE_VEHICLE = "Vehicle"
ENTITY_TYPE_LOCATION = "Location"
ENTITY_TYPE_FINANCIALACCOUNT = "FinancialAccount"
ENTITY_TYPE_TRANSACTION = "Transaction"
ENTITY_TYPE_COMMUNICATION = "Communication"
ENTITY_TYPE_CASE = "Case"
ENTITY_TYPE_FIR = "FIR"
ENTITY_TYPE_EVENT = "Event"
ENTITY_TYPE_EVIDENCE = "Evidence"

RELATIONSHIP_TYPES = sorted(CANONICAL_RELATIONSHIP_TYPES)

PERSON_FIRST_NAMES = [
    "Aarav", "Bella", "Chirag", "Devika", "Eshan", "Farah", "Girish",
    "Hema", "Imran", "Jaya", "Kabir", "Lata", "Meera", "Nikhil",
    "Ojas", "Priya", "Qadir", "Rhea", "Suresh", "Tara", "Ujjwal",
    "Vanya", "Wasim", "Xena", "Yusuf", "Zara", "Alok", "Bhavna",
    "Charu", "Dinesh", "Elina", "Faisal", "Gauri", "Harsh", "Isha",
]

PERSON_LAST_NAMES = [
    "Verma", "Sharma", "Patel", "Reddy", "Nair", "Iyer", "Bose",
    "Chatterjee", "Malhotra", "Kapoor", "Deshmukh", "Kulkarni",
    "Rao", "Menon", "Joshi", "Bhat", "Gupta", "Sinha", "Pillai",
    "Chauhan", "Mehta", "Sethi", "Dubey", "Pandey", "Ghosh",
]

ORG_SUFFIXES = [
    "Traders Pvt Ltd", "Logistics LLP", "Enterprises", "Services Ltd",
    "Imports & Exports", "Solutions Pvt Ltd", "Associates", "Industries Ltd",
]
ORG_PREFIXES = [
    "Bluepeak", "Silverline", "Northstar", "Greenfield", "Redwood",
    "Clearwater", "Ironvale", "Suncrest", "Windmere", "Stonebridge",
    "Fairmont", "Lakeshore", "Highgate", "Oakhurst",
]

PHONE_PREFIXES = ["+91-90", "+91-91", "+91-92", "+91-93", "+91-94"]
CARRIERS = ["FictionalTel A", "FictionalTel B", "FictionalTel C"]

VEHICLE_MAKES = ["Maruti", "Hyundai", "Tata", "Mahindra", "Honda", "Toyota"]
VEHICLE_MODELS = ["Swift D", "i10 N", "Nexon X", "Bolero M", "City V", "Etios L"]
VEHICLE_COLORS = ["White", "Silver", "Grey", "Black", "Blue"]
VEHICLE_STATES = ["DL", "UP", "HR", "MH", "KA"]

AREA_NAMES = [
    "Sector 12 Market", "Ring Road Junction", "Old Fort Road",
    "Lake View Colony", "Station Square", "Mill Lane",
    "Garden Chowk", "Riverside Depot", "Tech Park Gate",
    "Hillview Apartments",
]
CITY_NAMES = ["Fictionpur", "Demograd", "Sampleville", "Testnagar"]

FINANCIAL_INSTITUTIONS = [
    "Demo Bank of Fictionpur", "Sample Cooperative Bank",
    "Testnagar Commercial Bank", "Demograd Savings Society",
]

CASE_TYPES = ["financial_irregularity", "property_dispute", "cyber_fraud",
              "cargo_theft", "extortion_complaint"]
CASE_STATUSES = ["open", "under_investigation", "closed"]
COMM_MEDIUMS = ["call", "sms", "email", "chat"]
EXTRACTION_METHODS = ["cdr_record", "bank_statement_parse",
                      "patrol_log", "manual_entry", "pattern"]


def _seeded_epoch(seed: int) -> datetime:
    """Derive a fixed 'generation time' from the seed for determinism."""
    h = int(hashlib.sha256(str(seed).encode()).hexdigest()[:8], 16)
    return _GENESIS + timedelta(seconds=h % 86_400)


class SyntheticDataConfig:
    """Seeded, deterministic synthetic dataset generator."""

    def __init__(self, seed: int = RANDOM_SEED):
        self.seed = seed
        self.rng = random.Random(seed)
        self.generated_at = _seeded_epoch(seed)
        self.counters: Dict[str, int] = {}

    # --- ID generation -----------------------------------------------------

    def _next_id(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}-{self.counters[prefix]:05d}"

    def person_id(self) -> str:
        return self._next_id("person")

    def org_id(self) -> str:
        return self._next_id("org")

    def phone_id(self) -> str:
        return self._next_id("phone")

    def vehicle_id(self) -> str:
        return self._next_id("vehicle")

    def location_id(self) -> str:
        return self._next_id("location")

    def account_id(self) -> str:
        return self._next_id("account")

    def transaction_id(self) -> str:
        return self._next_id("transaction")

    def comm_id(self) -> str:
        return self._next_id("comm")

    def case_id(self) -> str:
        return self._next_id("case")

    def fir_id(self) -> str:
        return self._next_id("fir")

    def event_id(self) -> str:
        return self._next_id("event")

    def evidence_id(self) -> str:
        return self._next_id("evidence")

    def relationship_id(self) -> str:
        return self._next_id("rel")

    # --- Time helpers ------------------------------------------------------

    def ts_between(self, start: datetime, end: datetime) -> datetime:
        delta = int((end - start).total_seconds())
        return start + timedelta(seconds=self.rng.randint(0, max(delta, 0)))

    def iso(self, dt: Optional[datetime] = None) -> Optional[str]:
        if dt is None:
            return None
        return dt.isoformat().replace("+00:00", "Z")

    @property
    def created_at(self) -> str:
        """Deterministic record-creation time (derived from seed)."""
        return self.iso(self.generated_at)

    # --- Entity generators ---------------------------------------------------

    def generate_person(self) -> Dict[str, Any]:
        first = self.rng.choice(PERSON_FIRST_NAMES)
        last = self.rng.choice(PERSON_LAST_NAMES)
        dob_year = self.rng.randint(1965, 2003)
        return {
            "person_id": self.person_id(),
            "entity_id": None,  # filled below
            "entity_type": ENTITY_TYPE_PERSON,
            "full_name": f"{first} {last}",
            "date_of_birth": f"{dob_year}-{self.rng.randint(1, 12):02d}-{self.rng.randint(1, 28):02d}",
            "nationality": "IN (fictional)",
            "metadata": {"note": "synthetic person"},
            "created_at": self.created_at,
        }

    def generate_organization(self, name: Optional[str] = None) -> Dict[str, Any]:
        name = name or (
            self.rng.choice(ORG_PREFIXES) + " " + self.rng.choice(ORG_SUFFIXES)
        )
        return {
            "org_id": self.org_id(),
            "entity_id": None,
            "entity_type": ENTITY_TYPE_ORGANIZATION,
            "name": name,
            "registration_number": f"REG-FIC-{self.rng.randint(10000, 99999)}",
            "jurisdiction": "Fictional (India-like)",
            "metadata": {"employee_count": self.rng.randint(5, 300)},
            "created_at": self.created_at,
        }

    def generate_phone_number(self) -> Dict[str, Any]:
        number = f"{self.rng.choice(PHONE_PREFIXES)}-{self.rng.randint(1000000, 9999999)}"
        return {
            "phone_id": self.phone_id(),
            "entity_id": None,
            "entity_type": ENTITY_TYPE_PHONENUMBER,
            "number": number,  # fictional, reserved-style fictional ranges
            "phone_type": self.rng.choice(["mobile", "mobile", "landline"]),
            "carrier": self.rng.choice(CARRIERS),
            "metadata": {},
            "created_at": self.created_at,
        }

    def generate_vehicle(self) -> Dict[str, Any]:
        state = self.rng.choice(VEHICLE_STATES)
        reg = (f"{state}-FIC{self.rng.randint(1, 99):02d}-"
               f"{self.rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}"
               f"{self.rng.randint(1000, 9999)}")
        return {
            "vehicle_id": self.vehicle_id(),
            "entity_id": None,
            "entity_type": ENTITY_TYPE_VEHICLE,
            "registration_number": reg,  # FIC marker = guaranteed fictional
            "make": self.rng.choice(VEHICLE_MAKES),
            "model": self.rng.choice(VEHICLE_MODELS),
            "year": self.rng.randint(2010, 2024),
            "color": self.rng.choice(VEHICLE_COLORS),
            "vin": f"FIC{self.rng.randint(10**8, 10**9 - 1)}",
            "metadata": {},
            "created_at": self.created_at,
        }

    def generate_location(self) -> Dict[str, Any]:
        lat = round(self.rng.uniform(28.40, 28.75), 5)
        lng = round(self.rng.uniform(76.95, 77.35), 5)
        return {
            "location_id": self.location_id(),
            "entity_id": None,
            "entity_type": ENTITY_TYPE_LOCATION,
            "latitude": lat,
            "longitude": lng,
            "description": self.rng.choice(AREA_NAMES),
            "area_name": self.rng.choice(CITY_NAMES),
            "metadata": {"accuracy_meters": self.rng.randint(5, 60)},
            "created_at": self.created_at,
        }

    def generate_financial_account(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id(),
            "entity_id": None,
            "entity_type": ENTITY_TYPE_FINANCIALACCOUNT,
            "account_number": f"FICA{self.rng.randint(10**8, 10**9 - 1)}",
            "account_type": self.rng.choice(["checking", "savings"]),
            "institution": self.rng.choice(FINANCIAL_INSTITUTIONS),
            "jurisdiction": "Fictional (India-like)",
            "currency": "INR (fictional)",
            "metadata": {},
            "created_at": self.created_at,
        }

    # --- Relationship factory (canonical provenance) -------------------------

    def make_relationship(
        self,
        source_id: str,
        source_type: str,
        target_id: str,
        target_type: str,
        relationship_type: str,
        timestamp: Optional[datetime] = None,
        confidence: Optional[float] = None,
        extraction_method: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        assert source_id != target_id, "self-loop relationships are forbidden"
        assert relationship_type in CANONICAL_RELATIONSHIP_TYPES
        assert source_type in CANONICAL_ENTITY_TYPES
        assert target_type in CANONICAL_ENTITY_TYPES
        conf = confidence if confidence is not None else round(self.rng.uniform(0.55, 0.98), 2)
        method = extraction_method or self.rng.choice(EXTRACTION_METHODS)
        return {
            "relationship_id": self.relationship_id(),
            "source_id": source_id,
            "source_type": source_type,
            "target_id": target_id,
            "target_type": target_type,
            "relationship_type": relationship_type,
            "timestamp": self.iso(timestamp) if timestamp else None,
            "confidence": max(0.0, min(1.0, conf)),
            "extraction_method": method,
            "created_at": self.created_at,
            "metadata": metadata or {},
        }

    # --- Case / FIR / Event / Evidence ---------------------------------------

    def generate_case(self, index: int) -> Dict[str, Any]:
        opened = self.ts_between(
            _GENESIS, _GENESIS + timedelta(days=700))
        return {
            "case_id": self.case_id(),
            "entity_id": None,
            "entity_type": ENTITY_TYPE_CASE,
            "case_number": f"SYN-CASE-2024-{index:03d}",
            "title": f"Inquiry {index:03d} (synthetic)",
            "description": (
                "Synthetic investigation record for development only. "
                "Describes connections between fictional entities."
            ),
            "case_type": self.rng.choice(CASE_TYPES),
            "status": self.rng.choices(
                CASE_STATUSES, weights=[0.5, 0.3, 0.2])[0],
            "assigned_to": None,  # linked after persons exist
            "opened_at": self.iso(opened),
            "metadata": {"classification": "SYNTHETIC_DEMO"},
            "created_at": self.created_at,
        }

    def generate_fir(self, case_id: str, index: int) -> Dict[str, Any]:
        filed = self.ts_between(_GENESIS, _GENESIS + timedelta(days=730))
        return {
            "fir_id": self.fir_id(),
            "entity_id": None,
            "entity_type": ENTITY_TYPE_FIR,
            "fir_number": f"SYN-FIR-2024-{index:04d}",
            "case_id": case_id,
            "fir_type": self.rng.choice(["FIR", "complaint", "intel_report"]),
            "filed_at": self.iso(filed),
            "filed_by": None,  # linked after persons exist
            "jurisdiction": "Fictionpur (fictional PS)",
            "metadata": {},
            "created_at": self.created_at,
        }

    def generate_event(self, location_id: str) -> Dict[str, Any]:
        when = self.ts_between(_GENESIS, _GENESIS + timedelta(days=720))
        return {
            "event_id": self.event_id(),
            "entity_id": None,
            "entity_type": ENTITY_TYPE_EVENT,
            "name": f"Observed activity {self.rng.randint(100, 999)}",
            "description": "Synthetic observed event between fictional entities.",
            "event_type": self.rng.choice(["meeting", "sighting", "handoff", "travel"]),
            "timestamp": self.iso(when),
            "location_id": location_id,
            "metadata": {},
            "created_at": self.created_at,
        }

    def generate_evidence(self, case_id: str) -> Dict[str, Any]:
        collected = self.ts_between(_GENESIS, _GENESIS + timedelta(days=730))
        return {
            "evidence_id": self.evidence_id(),
            "entity_id": None,
            "entity_type": ENTITY_TYPE_EVIDENCE,
            "case_id": case_id,
            "description": "Synthetic evidence item (metadata only, no real content).",
            "evidence_type": self.rng.choice(
                ["document", "digital_record", "physical_item", "cdr_extract"]),
            "source": "Simulated collection point (fictional)",
            "collected_at": self.iso(collected),
            "collected_by": None,  # linked after persons exist
            "chain_hash": None,  # populated by blockchain module later
            "status": self.rng.choice(["logged", "in_custody", "under_review"]),
            "metadata": {"synthetic": True},
            "created_at": self.created_at,
        }

    # -------------------------------------------------------------------------
    # Full dataset
    # -------------------------------------------------------------------------

    def generate_full_dataset(
        self,
        num_persons: int = 30,
        num_organizations: int = 6,
        num_phones: int = 24,
        num_vehicles: int = 12,
        num_locations: int = 10,
        num_accounts: int = 14,
        num_transactions: int = 45,
        num_communications: int = 120,
        num_cases: int = 4,
        num_events: int = 25,
        num_evidence: int = 10,
    ) -> Dict[str, Any]:

        t0 = _GENESIS
        t1 = _GENESIS + timedelta(days=730)

        # 1. Base entities -----------------------------------------------------
        persons = [self.generate_person() for _ in range(num_persons)]
        orgs = [self.generate_organization() for _ in range(num_organizations)]
        phones = [self.generate_phone_number() for _ in range(num_phones)]
        vehicles = [self.generate_vehicle() for _ in range(num_vehicles)]
        locations = [self.generate_location() for _ in range(num_locations)]
        accounts = [self.generate_financial_account() for _ in range(num_accounts)]

        person_ids = [p["person_id"] for p in persons]
        rels: List[Dict[str, Any]] = []

        # 2. Communities + bridge nodes ----------------------------------------
        # Split persons into communities of ~5; fully connect inside each;
        # then wire a few designated BRIDGE persons between adjacent
        # communities so multi-hop paths exist across the graph.
        community_size = 5
        communities = [
            person_ids[i:i + community_size]
            for i in range(0, len(person_ids), community_size)
        ]
        for community in communities:
            for i in range(len(community)):
                for j in range(i + 1, len(community)):
                    when = self.ts_between(t0, t1)
                    rels.append(self.make_relationship(
                        community[i], ENTITY_TYPE_PERSON,
                        community[j], ENTITY_TYPE_PERSON,
                        "KNOWS", timestamp=when,
                        extraction_method="manual_entry"))
        # Bridges: connect each community's first member to next community's
        # first member (indirect cross-community paths become possible).
        bridges = []
        for a, b in zip(communities, communities[1:]):
            when = self.ts_between(t0, t1)
            rels.append(self.make_relationship(
                a[0], ENTITY_TYPE_PERSON, b[0], ENTITY_TYPE_PERSON,
                "KNOWS", timestamp=when, confidence=0.72,
                extraction_method="pattern"))
            bridges.append(a[0])

        # 3. Phone ownership + repeated communication pairs ----------------------
        person_phone: Dict[str, List[str]] = {}
        for idx, phone in enumerate(phones):
            owner = person_ids[idx % len(person_ids)]
            person_phone.setdefault(owner, []).append(phone["phone_id"])
            rels.append(self.make_relationship(
                owner, ENTITY_TYPE_PERSON,
                phone["phone_id"], ENTITY_TYPE_PHONENUMBER,
                "OWNS", confidence=0.97, extraction_method="cdr_record"))

        # 4. Communications (repeated-contact pattern + hub chatter) -------------
        comms: List[Dict[str, Any]] = []
        # Pick a few stable pairs that communicate repeatedly (temporal signal)
        repeat_pairs = []
        for c in communities:
            if len(c) >= 2:
                repeat_pairs.append((c[0], c[1]))
                repeat_pairs.append((c[2 % len(c)], c[3 % len(c)]))

        for i in range(num_communications):
            if i < len(repeat_pairs) * 6:
                src, dst = repeat_pairs[i % len(repeat_pairs)]
            else:
                src = self.rng.choice(person_ids)
                dst = self.rng.choice([p for p in person_ids if p != src])
            medium = self.rng.choice(COMM_MEDIUMS)
            via_phone = medium in ("call", "sms")
            comm = {
                "comm_id": self.comm_id(),
                "entity_id": None,
                "entity_type": ENTITY_TYPE_COMMUNICATION,
                "medium": medium,
                "direction": self.rng.choice(["outgoing", "incoming"]),
                "from_entity_id": src,
                "to_entity_id": dst,
                "from_phone_id": person_phone[src][0] if via_phone and person_phone.get(src) else None,
                "to_phone_id": person_phone[dst][0] if via_phone and person_phone.get(dst) else None,
                "timestamp": self.iso(self.ts_between(t0, t1)),
                "duration_seconds": self.rng.randint(20, 1800) if medium == "call" else None,
                "metadata": {"synthetic": True},
                "created_at": self.created_at,
            }
            comms.append(comm)
            rels.append(self.make_relationship(
                src, ENTITY_TYPE_PERSON, dst, ENTITY_TYPE_PERSON,
                "CALLED", timestamp=datetime.fromisoformat(comm["timestamp"].replace("Z", "+00:00")),
                confidence=0.95, extraction_method="cdr_record",
                metadata={"comm_id": comm["comm_id"]}))

        # 5. Employment / association -------------------------------------------
        for i, pid in enumerate(person_ids):
            org = orgs[i % len(orgs)]
            rtype = "WORKS_FOR" if i % 3 != 2 else "ASSOCIATED_WITH"
            rels.append(self.make_relationship(
                pid, ENTITY_TYPE_PERSON, org["org_id"],
                ENTITY_TYPE_ORGANIZATION, rtype,
                confidence=0.85, extraction_method="manual_entry"))

        # 6. Vehicles: ownership vs usage (some shared usage = co-use signal) ----
        for i, pid in enumerate(person_ids):
            v = vehicles[i % len(vehicles)]
            rels.append(self.make_relationship(
                pid, ENTITY_TYPE_PERSON, v["vehicle_id"],
                ENTITY_TYPE_VEHICLE, "OWNS",
                confidence=0.9, extraction_method="manual_entry"))
        # A few persons USE vehicles they do not own (bridge-ish behavior)
        for k in range(min(8, num_persons)):
            user = person_ids[(k * 7 + 3) % num_persons]
            v = vehicles[(k * 5 + 2) % num_vehicles]
            rels.append(self.make_relationship(
                user, ENTITY_TYPE_PERSON, v["vehicle_id"],
                ENTITY_TYPE_VEHICLE, "USED",
                timestamp=self.ts_between(t0, t1),
                confidence=0.66, extraction_method="patrol_log"))

        # 7. Locations: residence vs travel ---------------------------------------
        home_of: Dict[str, str] = {}
        for i, pid in enumerate(person_ids):
            loc = locations[i % len(locations)]
            home_of[pid] = loc["location_id"]
            rels.append(self.make_relationship(
                pid, ENTITY_TYPE_PERSON, loc["location_id"],
                ENTITY_TYPE_LOCATION, "LOCATED_AT",
                confidence=0.88, extraction_method="manual_entry"))
        for pid in person_ids[:num_persons // 2]:
            others = [l["location_id"] for l in locations
                      if l["location_id"] != home_of[pid]]
            rels.append(self.make_relationship(
                pid, ENTITY_TYPE_PERSON, self.rng.choice(others),
                ENTITY_TYPE_LOCATION, "TRAVELED_TO",
                timestamp=self.ts_between(t0, t1),
                confidence=0.7, extraction_method="patrol_log"))

        # 8. Accounts owned by persons --------------------------------------------
        acct_owner: Dict[str, str] = {}
        for i, acct in enumerate(accounts):
            owner = person_ids[i % len(person_ids)]
            acct_owner[acct["account_id"]] = owner
            rels.append(self.make_relationship(
                owner, ENTITY_TYPE_PERSON, acct["account_id"],
                ENTITY_TYPE_FINANCIALACCOUNT, "OWNS",
                confidence=0.93, extraction_method="bank_statement_parse"))

        # 9. Transactions: layered chains + one unusual burst ---------------------
        transactions: List[Dict[str, Any]] = []
        chain_accounts = [a["account_id"] for a in accounts]
        base_time = t0 + timedelta(days=30)
        for i in range(num_transactions):
            if i < num_transactions - 6:
                # normal-ish flow along rotating chains
                frm = chain_accounts[i % len(chain_accounts)]
                to = chain_accounts[(i + 3) % len(chain_accounts)]
                amount = round(self.rng.uniform(2_000, 80_000), 2)
                when = self.ts_between(base_time, t1)
            else:
                # UNUSUAL BEHAVIOR: rapid same-day round-robin of near-equal
                # amounts through 3 accounts (layering-like demo pattern).
                trio = chain_accounts[:3]
                frm = trio[i % 3]
                to = trio[(i + 1) % 3]
                amount = 49_500.00 + self.rng.randint(0, 400)
                day = _GENESIS + timedelta(days=400)
                when = day + timedelta(hours=i % 6)
            txn = {
                "transaction_id": self.transaction_id(),
                "entity_id": None,
                "entity_type": ENTITY_TYPE_TRANSACTION,
                "amount": amount,
                "transaction_type": "transfer",
                "currency": "INR (fictional)",
                "from_account_id": frm,
                "to_account_id": to,
                "timestamp": self.iso(when),
                "description": "Synthetic transfer record (demo)",
                "is_flagged_demo": i >= num_transactions - 6,
                "metadata": {},
                "created_at": self.created_at,
            }
            transactions.append(txn)
            rels.append(self.make_relationship(
                frm, ENTITY_TYPE_FINANCIALACCOUNT, to,
                ENTITY_TYPE_FINANCIALACCOUNT, "TRANSFERRED_TO",
                timestamp=when, confidence=0.99,
                extraction_method="bank_statement_parse",
                metadata={"transaction_id": txn["transaction_id"],
                          "amount": amount}))

        # 10. Cases, FIRs, events, evidence + case links ---------------------------
        officer_ids = person_ids[:max(2, num_persons // 10)]
        cases = []
        for ci in range(num_cases):
            case = self.generate_case(ci + 1)
            case["assigned_to"] = self.rng.choice(officer_ids)
            cases.append(case)

        firs = []
        for fi in range(max(num_cases, 4)):
            case = cases[fi % len(cases)]
            fir = self.generate_fir(case["case_id"], fi + 1)
            fir["filed_by"] = self.rng.choice(officer_ids)
            firs.append(fir)

        events = []
        for _ in range(num_events):
            ev = self.generate_event(self.rng.choice(locations)["location_id"])
            events.append(ev)

        evidence = []
        for case in cases:
            for _ in range(max(1, num_evidence // num_cases)):
                evd = self.generate_evidence(case["case_id"])
                evd["collected_by"] = self.rng.choice(officer_ids)
                evidence.append(evd)

        # Case linkage relationships
        for case in cases:
            for pid in self.rng.sample(person_ids, k=min(6, num_persons)):
                rels.append(self.make_relationship(
                    pid, ENTITY_TYPE_PERSON, case["case_id"],
                    ENTITY_TYPE_CASE, "MENTIONED_IN",
                    confidence=0.8, extraction_method="manual_entry"))
            org_pick = self.rng.choice(orgs)
            rels.append(self.make_relationship(
                org_pick["org_id"], ENTITY_TYPE_ORGANIZATION,
                case["case_id"], ENTITY_TYPE_CASE, "MENTIONED_IN",
                confidence=0.75, extraction_method="manual_entry"))
            # evidence related to its case
        for evd in evidence:
            rels.append(self.make_relationship(
                evd["evidence_id"], ENTITY_TYPE_EVIDENCE,
                evd["case_id"], ENTITY_TYPE_CASE,
                "RELATED_TO_CASE", confidence=1.0,
                extraction_method="manual_entry"))
        for fir in firs:
            rels.append(self.make_relationship(
                fir["fir_id"], ENTITY_TYPE_FIR,
                fir["case_id"], ENTITY_TYPE_CASE,
                "RELATED_TO_CASE", confidence=1.0,
                extraction_method="manual_entry"))
        for ev in events:
            rels.append(self.make_relationship(
                ev["event_id"], ENTITY_TYPE_EVENT,
                ev["location_id"], ENTITY_TYPE_LOCATION,
                "LOCATED_AT", timestamp=datetime.fromisoformat(
                    ev["timestamp"].replace("Z", "+00:00")),
                confidence=0.9, extraction_method="patrol_log"))

        # Fill uniform entity_id field on all entities
        for e in persons:
            e["entity_id"] = e["person_id"]
        for e in orgs:
            e["entity_id"] = e["org_id"]
        for e in phones:
            e["entity_id"] = e["phone_id"]
        for e in vehicles:
            e["entity_id"] = e["vehicle_id"]
        for e in locations:
            e["entity_id"] = e["location_id"]
        for e in accounts:
            e["entity_id"] = e["account_id"]
        for e in transactions:
            e["entity_id"] = e["transaction_id"]
        for e in comms:
            e["entity_id"] = e["comm_id"]
        for e in cases:
            e["entity_id"] = e["case_id"]
        for e in firs:
            e["entity_id"] = e["fir_id"]
        for e in events:
            e["entity_id"] = e["event_id"]
        for e in evidence:
            e["entity_id"] = e["evidence_id"]

        return {
            "persons": persons,
            "organizations": orgs,
            "phone_numbers": phones,
            "vehicles": vehicles,
            "locations": locations,
            "financial_accounts": accounts,
            "transactions": transactions,
            "communications": comms,
            "cases": cases,
            "firs": firs,
            "events": events,
            "evidence": evidence,
            "relationships": rels,
            "generation_config": {
                "seed": self.seed,
                "generated_at_deterministic": self.created_at,
                "counts": {
                    "persons": len(persons),
                    "organizations": len(orgs),
                    "phone_numbers": len(phones),
                    "vehicles": len(vehicles),
                    "locations": len(locations),
                    "financial_accounts": len(accounts),
                    "transactions": len(transactions),
                    "communications": len(comms),
                    "cases": len(cases),
                    "firs": len(firs),
                    "events": len(events),
                    "evidence": len(evidence),
                    "relationships": len(rels),
                },
                "patterns": [
                    "direct_relationships", "indirect_relationships",
                    "communities", "bridge_nodes", "repeated_communications",
                    "transaction_chains", "temporal_activity",
                    "unusual_behavior_demo",
                ],
                "safety_notice": (
                    "All data is fictional. No real PII, no real cases. "
                    "System assists investigators; it never labels "
                    "individuals as criminals."
                ),
            },
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

DEFAULT_COUNTS = dict(
    num_persons=30, num_organizations=6, num_phones=24, num_vehicles=12,
    num_locations=10, num_accounts=14, num_transactions=45,
    num_communications=120, num_cases=4, num_events=25, num_evidence=10,
)


def build_dataset(seed: int = RANDOM_SEED, **overrides) -> Dict[str, Any]:
    counts = dict(DEFAULT_COUNTS)
    counts.update({k: v for k, v in overrides.items() if v is not None})
    cfg = SyntheticDataConfig(seed=seed)
    return cfg.generate_full_dataset(**counts)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="SIH 26189 deterministic synthetic data generator")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--output", default="data/synthetic")
    parser.add_argument("--single-file", action="store_true",
                        help="Write one combined JSON instead of per-type files")
    for key in DEFAULT_COUNTS:
        parser.add_argument(f"--{key.replace('num_', '')}", type=int, default=None)
    args = parser.parse_args()

    overrides = {}
    for key in DEFAULT_COUNTS:
        val = getattr(args, key.replace("num_", ""))
        if val is not None:
            overrides[key] = val

    dataset = build_dataset(seed=args.seed, **overrides)
    os.makedirs(args.output, exist_ok=True)

    if args.single_file:
        path = os.path.join(args.output, "synthetic_dataset.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        print(f"Wrote {path}")
    else:
        for key, rows in dataset.items():
            if key == "generation_config":
                continue
            fname = f"{key}.json"
            path = os.path.join(args.output, fname)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2, ensure_ascii=False)
            print(f"Wrote {path} ({len(rows)} records)")
        cfg_path = os.path.join(args.output, "_generation_config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(dataset["generation_config"], f, indent=2)
        print(f"Wrote {cfg_path}")

    counts = dataset["generation_config"]["counts"]
    print("Summary:", json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
