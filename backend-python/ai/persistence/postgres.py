"""PostgreSQL persistence — canonical store (Milestone 4).

Implements PersistenceBase against db/001_initial_schema.sql (TEXT IDs,
no UUIDs). All writes are parameterized, idempotent (ON CONFLICT DO UPDATE),
and transaction-safe.

Driver: tries `psycopg` (v3) first, then `psycopg2`. If neither is installed,
construction raises PersistenceError with instructions.

Env:
    DATABASE_URL / APP_DATABASE_URL / POSTGRES_* vars
    Default fallback: postgresql://investigator:secure_password@localhost:5432/criminal_network
                    (matches docker-compose.yml postgres service)

Provenance: every relationship preserves relationship_id, source_id,
source_type, target_id, target_type, timestamp, confidence, extraction_method,
created_at, source_id (doc), metadata.

Transaction usage:
    with persistence.transaction():
        persistence.save_entity(...)
        persistence.save_relationship(...)
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import PersistenceBase, PersistenceError

# ---------------------------------------------------------------------------
# Driver detection (lazy)
# ---------------------------------------------------------------------------

_psycopg = None
_psycopg2 = None
_driver_name: Optional[str] = None

try:  # psycopg 3 (preferred)
    import psycopg as _psycopg  # type: ignore

    _driver_name = "psycopg"
except ImportError:
    try:
        import psycopg2 as _psycopg2  # type: ignore
        import psycopg2.extras as _psycopg2_extras  # type: ignore

        _driver_name = "psycopg2"
    except ImportError:
        _driver_name = None

# ---------------------------------------------------------------------------
# Table routing for 12 entity types
# ---------------------------------------------------------------------------

# Maps canonical entity_type -> (table, pk_column)
ENTITY_TABLE_MAP: Dict[str, Tuple[str, str]] = {
    "Person": ("persons", "person_id"),
    "Organization": ("organizations", "org_id"),
    "PhoneNumber": ("phone_numbers", "phone_id"),
    "Vehicle": ("vehicles", "vehicle_id"),
    "Location": ("locations", "location_id"),
    "FinancialAccount": ("financial_accounts", "account_id"),
    "Transaction": ("transactions", "transaction_id"),
    "Communication": ("communications", "comm_id"),
    "Case": ("cases", "case_id"),
    "FIR": ("firs", "fir_id"),
    "Event": ("events", "event_id"),
    "Evidence": ("evidence", "evidence_id"),
}

# Reverse prefix -> entity_type for get_entity lookup
PREFIX_TO_TYPE = {
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


def _infer_type_from_id(entity_id: str) -> Optional[str]:
    prefix = entity_id.split("-")[0] if "-" in entity_id else ""
    return PREFIX_TO_TYPE.get(prefix)


def _dsn_from_env(explicit_dsn: Optional[str] = None) -> str:
    if explicit_dsn:
        # Ensure connect_timeout for fast failure when DB unavailable
        if "connect_timeout" not in explicit_dsn:
            sep = "&" if "?" in explicit_dsn else "?"
            return f"{explicit_dsn}{sep}connect_timeout=2"
        return explicit_dsn
    for key in ("DATABASE_URL", "APP_DATABASE_URL", "POSTGRES_URL"):
        val = os.getenv(key)
        if val:
            if "connect_timeout" not in val:
                sep = "&" if "?" in val else "?"
                return f"{val}{sep}connect_timeout=2"
            return val
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", os.getenv("APP_POSTGRES_USER", "investigator"))
    password = os.getenv("POSTGRES_PASSWORD", os.getenv("APP_POSTGRES_PASSWORD", "secure_password"))
    db = os.getenv("POSTGRES_DB", os.getenv("APP_POSTGRES_DB", "criminal_network"))
    return f"postgresql://{user}:{password}@{host}:{port}/{db}?connect_timeout=2"


class PostgresPersistence(PersistenceBase):
    """PostgreSQL-backed canonical persistence."""

    def __init__(self, dsn: Optional[str] = None, autocommit: bool = True) -> None:
        if _driver_name is None:
            raise PersistenceError(
                "Neither 'psycopg' nor 'psycopg2' is installed. "
                "Install with: pip install \"psycopg[binary]\" or pip install psycopg2-binary"
            )
        self.dsn = _dsn_from_env(dsn)
        self._conn = None  # type: ignore
        self._in_transaction = False
        self.autocommit = autocommit
        # Validate connection lazily; health_check does real verification

    # -- connection helpers -------------------------------------------------

    def _connect(self):
        if self._conn is not None and not getattr(self._conn, "closed", 0):
            return self._conn
        if _driver_name == "psycopg":
            self._conn = _psycopg.connect(self.dsn, autocommit=self.autocommit)  # type: ignore
        else:
            self._conn = _psycopg2.connect(self.dsn)  # type: ignore
            if self.autocommit:
                self._conn.autocommit = True  # type: ignore
        return self._conn

    def _execute(self, sql: str, params: tuple = ()):
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            return cur
        except Exception as exc:
            # Do not log password/DSN
            raise PersistenceError(f"SQL execution failed: {exc}") from exc

    def _fetchone(self, sql: str, params: tuple = ()):
        cur = self._execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row

    def _fetchall(self, sql: str, params: tuple = ()):
        cur = self._execute(sql, params)
        rows = cur.fetchall()
        # Get column names if available
        colnames = [d[0] for d in cur.description] if cur.description else []
        cur.close()
        return rows, colnames

    # -- health / schema ----------------------------------------------------

    def health_check(self) -> bool:
        try:
            cur = self._execute("SELECT 1")
            cur.close()
            # Also verify relationships table exists
            cur2 = self._execute("SELECT to_regclass('public.relationships')")
            exists = cur2.fetchone()
            cur2.close()
            return exists is not None and exists[0] is not None
        except PersistenceError:
            return False
        except Exception:
            return False

    def init_schema(self, schema_path: Optional[Path] = None) -> None:
        """Apply db/001_initial_schema.sql idempotently."""
        if schema_path is None:
            # Resolve relative to project root
            base = Path(__file__).resolve().parents[2]
            schema_path = base / "db" / "001_initial_schema.sql"
        if not schema_path.exists():
            raise PersistenceError(f"Schema file not found: {schema_path}")
        sql = schema_path.read_text(encoding="utf-8")
        conn = self._connect()
        # Use transaction for schema
        orig_autocommit = getattr(conn, "autocommit", True)
        try:
            if hasattr(conn, "autocommit"):
                conn.autocommit = False  # type: ignore
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise PersistenceError(f"Schema init failed: {exc}") from exc
        finally:
            if hasattr(conn, "autocommit"):
                conn.autocommit = orig_autocommit  # type: ignore

    # -- entity writes ------------------------------------------------------

    def save_entity(self, entity_id: str, entity_type: str, payload: Dict[str, Any]) -> str:
        if entity_type not in ENTITY_TABLE_MAP:
            raise PersistenceError(f"Unknown entity_type '{entity_type}'")
        table, pk = ENTITY_TABLE_MAP[entity_type]
        # Dispatch to type-specific upsert
        if entity_type == "Person":
            return self._upsert_person(entity_id, payload)
        if entity_type == "Organization":
            return self._upsert_organization(entity_id, payload)
        if entity_type == "PhoneNumber":
            return self._upsert_phone(entity_id, payload)
        if entity_type == "Vehicle":
            return self._upsert_vehicle(entity_id, payload)
        if entity_type == "Location":
            return self._upsert_location(entity_id, payload)
        if entity_type == "FinancialAccount":
            return self._upsert_account(entity_id, payload)
        if entity_type == "Transaction":
            return self._upsert_transaction(entity_id, payload)
        if entity_type == "Communication":
            return self._upsert_communication(entity_id, payload)
        if entity_type == "Case":
            return self._upsert_case(entity_id, payload)
        if entity_type == "FIR":
            return self._upsert_fir(entity_id, payload)
        if entity_type == "Event":
            return self._upsert_event(entity_id, payload)
        if entity_type == "Evidence":
            return self._upsert_evidence(entity_id, payload)
        # Fallback generic (should not happen)
        return self._generic_upsert(table, pk, entity_id, payload)

    # -- entity upsert helpers (all parameterized, ON CONFLICT) -------------

    def _upsert_person(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO persons (person_id, full_name, date_of_birth, nationality, metadata, created_at)
        VALUES (%s, %s, %s::date, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (person_id) DO UPDATE SET
            full_name = EXCLUDED.full_name,
            date_of_birth = EXCLUDED.date_of_birth,
            nationality = EXCLUDED.nationality,
            metadata = EXCLUDED.metadata
        RETURNING (xmax = 0) AS inserted
        """
        full_name = p.get("full_name") or p.get("text") or p.get("name") or "Unknown"
        dob = p.get("date_of_birth")
        nationality = p.get("nationality")
        metadata = json.dumps(p.get("metadata", {}))
        created_at = p.get("created_at")
        cur = self._execute(sql, (entity_id, full_name, dob, nationality, metadata, created_at))
        inserted = cur.fetchone()[0] if cur.rowcount else True
        cur.close()
        if not self._in_transaction and self.autocommit:
            self._connect().commit() if hasattr(self._connect(), "commit") else None
        return "inserted" if inserted else "updated"

    def _upsert_organization(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO organizations (org_id, name, org_type, registration_number, jurisdiction, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (org_id) DO UPDATE SET
            name = EXCLUDED.name,
            org_type = EXCLUDED.org_type,
            registration_number = EXCLUDED.registration_number,
            jurisdiction = EXCLUDED.jurisdiction,
            metadata = EXCLUDED.metadata
        RETURNING (xmax = 0) AS inserted
        """
        name = p.get("name") or p.get("text") or p.get("full_name") or "Unknown Org"
        org_type = p.get("org_type")
        reg = p.get("registration_number")
        juris = p.get("jurisdiction")
        metadata = json.dumps(p.get("metadata", {}))
        created_at = p.get("created_at")
        cur = self._execute(sql, (entity_id, name, org_type, reg, juris, metadata, created_at))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def _upsert_phone(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO phone_numbers (phone_id, number, phone_type, carrier, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (phone_id) DO UPDATE SET
            number = EXCLUDED.number,
            phone_type = EXCLUDED.phone_type,
            carrier = EXCLUDED.carrier,
            metadata = EXCLUDED.metadata
        RETURNING (xmax = 0) AS inserted
        """
        number = p.get("number") or p.get("text") or p.get("normalized_value") or ""
        phone_type = p.get("phone_type")
        carrier = p.get("carrier")
        metadata = json.dumps(p.get("metadata", {}))
        created_at = p.get("created_at")
        cur = self._execute(sql, (entity_id, number, phone_type, carrier, metadata, created_at))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def _upsert_vehicle(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO vehicles (vehicle_id, registration_number, make, model, year, color, vin, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (vehicle_id) DO UPDATE SET
            registration_number = EXCLUDED.registration_number,
            make = EXCLUDED.make,
            model = EXCLUDED.model,
            year = EXCLUDED.year,
            color = EXCLUDED.color,
            vin = EXCLUDED.vin,
            metadata = EXCLUDED.metadata
        RETURNING (xmax = 0) AS inserted
        """
        reg = p.get("registration_number") or p.get("text") or ""
        make = p.get("make") or "Unknown"
        model = p.get("model") or "Unknown"
        year = p.get("year") or 2020
        color = p.get("color")
        vin = p.get("vin")
        metadata = json.dumps(p.get("metadata", {}))
        created_at = p.get("created_at")
        cur = self._execute(sql, (entity_id, reg, make, model, year, color, vin, metadata, created_at))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def _upsert_location(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO locations (location_id, latitude, longitude, description, area_name, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (location_id) DO UPDATE SET
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            description = EXCLUDED.description,
            area_name = EXCLUDED.area_name,
            metadata = EXCLUDED.metadata
        RETURNING (xmax = 0) AS inserted
        """
        lat = p.get("latitude") or 28.5
        lng = p.get("longitude") or 77.1
        desc = p.get("description") or p.get("text") or ""
        area = p.get("area_name")
        metadata = json.dumps(p.get("metadata", {}))
        created_at = p.get("created_at")
        cur = self._execute(sql, (entity_id, lat, lng, desc, area, metadata, created_at))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def _upsert_account(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO financial_accounts (account_id, account_number, account_type, institution, jurisdiction, currency, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (account_id) DO UPDATE SET
            account_number = EXCLUDED.account_number,
            account_type = EXCLUDED.account_type,
            institution = EXCLUDED.institution,
            jurisdiction = EXCLUDED.jurisdiction,
            currency = EXCLUDED.currency,
            metadata = EXCLUDED.metadata
        RETURNING (xmax = 0) AS inserted
        """
        acct = p.get("account_number") or p.get("text") or ""
        acct_type = p.get("account_type")
        institution = p.get("institution")
        juris = p.get("jurisdiction")
        currency = p.get("currency") or "INR"
        metadata = json.dumps(p.get("metadata", {}))
        created_at = p.get("created_at")
        cur = self._execute(sql, (entity_id, acct, acct_type, institution, juris, currency, metadata, created_at))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def _upsert_transaction(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO transactions (transaction_id, amount, transaction_type, currency, from_account_id, to_account_id, timestamp, is_flagged_demo, description, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s::timestamptz, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (transaction_id) DO UPDATE SET
            amount = EXCLUDED.amount,
            transaction_type = EXCLUDED.transaction_type,
            currency = EXCLUDED.currency,
            from_account_id = EXCLUDED.from_account_id,
            to_account_id = EXCLUDED.to_account_id,
            timestamp = EXCLUDED.timestamp,
            is_flagged_demo = EXCLUDED.is_flagged_demo,
            description = EXCLUDED.description,
            metadata = EXCLUDED.metadata
        RETURNING (xmax = 0) AS inserted
        """
        amount = p.get("amount") or 0
        tx_type = p.get("transaction_type") or "transfer"
        currency = p.get("currency") or "INR"
        from_acct = p.get("from_account_id")
        to_acct = p.get("to_account_id")
        ts = p.get("timestamp")
        flagged = p.get("is_flagged_demo", False)
        desc = p.get("description")
        metadata = json.dumps(p.get("metadata", {}))
        created_at = p.get("created_at")
        cur = self._execute(sql, (entity_id, amount, tx_type, currency, from_acct, to_acct, ts, flagged, desc, metadata, created_at))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def _upsert_communication(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO communications (comm_id, medium, direction, from_entity_type, from_entity_id, to_entity_type, to_entity_id, from_phone_id, to_phone_id, timestamp, duration_seconds, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::timestamptz, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (comm_id) DO UPDATE SET
            medium = EXCLUDED.medium,
            direction = EXCLUDED.direction,
            from_entity_type = EXCLUDED.from_entity_type,
            from_entity_id = EXCLUDED.from_entity_id,
            to_entity_type = EXCLUDED.to_entity_type,
            to_entity_id = EXCLUDED.to_entity_id,
            from_phone_id = EXCLUDED.from_phone_id,
            to_phone_id = EXCLUDED.to_phone_id,
            timestamp = EXCLUDED.timestamp,
            duration_seconds = EXCLUDED.duration_seconds,
            metadata = EXCLUDED.metadata
        RETURNING (xmax = 0) AS inserted
        """
        # Synthetic comms store type as generic; map entity_type if present
        from_type = p.get("from_entity_type") or "Person"
        to_type = p.get("to_entity_type") or "Person"
        cur = self._execute(sql, (
            entity_id,
            p.get("medium") or "call",
            p.get("direction") or "outgoing",
            from_type, p.get("from_entity_id"),
            to_type, p.get("to_entity_id"),
            p.get("from_phone_id"), p.get("to_phone_id"),
            p.get("timestamp"), p.get("duration_seconds"),
            json.dumps(p.get("metadata", {})),
            p.get("created_at"),
        ))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def _upsert_case(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO cases (case_id, case_number, title, description, case_type, status, assigned_to, opened_at, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s::case_status, %s, %s::timestamptz, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (case_id) DO UPDATE SET
            case_number = EXCLUDED.case_number,
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            case_type = EXCLUDED.case_type,
            status = EXCLUDED.status,
            assigned_to = EXCLUDED.assigned_to,
            opened_at = EXCLUDED.opened_at,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING (xmax = 0) AS inserted
        """
        case_number = p.get("case_number") or entity_id
        title = p.get("title") or "Untitled"
        desc = p.get("description")
        case_type = p.get("case_type")
        status = p.get("status") or "open"
        assigned = p.get("assigned_to")
        opened = p.get("opened_at")
        metadata = json.dumps(p.get("metadata", {}))
        created_at = p.get("created_at")
        cur = self._execute(sql, (entity_id, case_number, title, desc, case_type, status, assigned, opened, metadata, created_at))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def _upsert_fir(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO firs (fir_id, fir_number, case_id, fir_type, filed_at, filed_by, jurisdiction, metadata, created_at)
        VALUES (%s, %s, %s, %s::fir_type, %s::timestamptz, %s, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (fir_id) DO UPDATE SET
            fir_number = EXCLUDED.fir_number,
            case_id = EXCLUDED.case_id,
            fir_type = EXCLUDED.fir_type,
            filed_at = EXCLUDED.filed_at,
            filed_by = EXCLUDED.filed_by,
            jurisdiction = EXCLUDED.jurisdiction,
            metadata = EXCLUDED.metadata
        RETURNING (xmax = 0) AS inserted
        """
        fir_number = p.get("fir_number") or entity_id
        case_id = p.get("case_id")
        fir_type = p.get("fir_type") or "FIR"
        filed_at = p.get("filed_at")
        filed_by = p.get("filed_by")
        juris = p.get("jurisdiction")
        metadata = json.dumps(p.get("metadata", {}))
        created_at = p.get("created_at")
        cur = self._execute(sql, (entity_id, fir_number, case_id, fir_type, filed_at, filed_by, juris, metadata, created_at))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def _upsert_event(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO events (event_id, name, description, event_type, timestamp, location_id, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s::timestamptz, %s, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (event_id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            event_type = EXCLUDED.event_type,
            timestamp = EXCLUDED.timestamp,
            location_id = EXCLUDED.location_id,
            metadata = EXCLUDED.metadata
        RETURNING (xmax = 0) AS inserted
        """
        name = p.get("name") or p.get("title") or "Event"
        desc = p.get("description")
        ev_type = p.get("event_type")
        ts = p.get("timestamp")
        loc = p.get("location_id")
        metadata = json.dumps(p.get("metadata", {}))
        created_at = p.get("created_at")
        cur = self._execute(sql, (entity_id, name, desc, ev_type, ts, loc, metadata, created_at))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def _upsert_evidence(self, entity_id: str, p: Dict[str, Any]) -> str:
        sql = """
        INSERT INTO evidence (evidence_id, case_id, description, evidence_type, source, collected_at, collected_by, chain_hash, status, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s::timestamptz, %s, %s, %s::evidence_status, %s::jsonb, COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (evidence_id) DO UPDATE SET
            case_id = EXCLUDED.case_id,
            description = EXCLUDED.description,
            evidence_type = EXCLUDED.evidence_type,
            source = EXCLUDED.source,
            collected_at = EXCLUDED.collected_at,
            collected_by = EXCLUDED.collected_by,
            chain_hash = EXCLUDED.chain_hash,
            status = EXCLUDED.status,
            metadata = EXCLUDED.metadata
        RETURNING (xmax = 0) AS inserted
        """
        case_id = p.get("case_id")
        desc = p.get("description")
        ev_type = p.get("evidence_type")
        source = p.get("source")
        collected_at = p.get("collected_at")
        collected_by = p.get("collected_by")
        chain_hash = p.get("chain_hash")
        # Deterministic chain_hash if not supplied: hash of canonical evidence representation
        if not chain_hash:
            try:
                from blockchain.evidence_chain import compute_evidence_chain_hash
                # Use previous hash from DB if available, else "0"
                prev_hash = "0"
                try:
                    # Try to fetch last evidence chain_hash for linkage (best effort, fallback to 0)
                    last_rows, _ = self._fetchall("SELECT chain_hash FROM evidence WHERE chain_hash IS NOT NULL ORDER BY created_at DESC LIMIT 1", ())
                    if last_rows and last_rows[0][0]:
                        prev_hash = last_rows[0][0]
                except Exception:
                    prev_hash = "0"
                chain_hash = compute_evidence_chain_hash(entity_id, p, prev_hash)
            except Exception:
                chain_hash = None
        status = p.get("status") or "logged"
        metadata = json.dumps(p.get("metadata", {}))
        created_at = p.get("created_at")
        cur = self._execute(sql, (entity_id, case_id, desc, ev_type, source, collected_at, collected_by, chain_hash, status, metadata, created_at))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def _generic_upsert(self, table: str, pk: str, entity_id: str, payload: Dict[str, Any]) -> str:
        # Fallback: store payload as metadata jsonb if table not explicitly handled
        sql = f"INSERT INTO {table} ({pk}, metadata) VALUES (%s, %s::jsonb) ON CONFLICT ({pk}) DO UPDATE SET metadata = EXCLUDED.metadata RETURNING (xmax = 0) AS inserted"
        cur = self._execute(sql, (entity_id, json.dumps(payload)))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    # -- relationship -------------------------------------------------------

    def save_relationship(self, relationship_id: str, payload: Dict[str, Any]) -> str:
        # Normalize payload: may be nested (source/target dict) or flat
        source_id = payload.get("source_id")
        source_type = payload.get("source_type")
        target_id = payload.get("target_id")
        target_type = payload.get("target_type")
        # Handle nested RuleRelationship.to_dict format
        if "source" in payload and isinstance(payload["source"], dict):
            source_id = payload["source"].get("entity_id") or source_id
            source_type = payload["source"].get("entity_type") or source_type
        if "target" in payload and isinstance(payload["target"], dict):
            target_id = payload["target"].get("entity_id") or target_id
            target_type = payload["target"].get("entity_type") or target_type
        relationship_type = payload.get("relationship_type") or "RELATED_TO_CASE"
        timestamp = payload.get("timestamp")
        confidence = payload.get("confidence", 0.5)
        extraction_method = payload.get("extraction_method") or "unknown"
        created_at = payload.get("created_at")
        metadata = json.dumps(payload.get("metadata", {}))

        if not source_id or not target_id:
            raise PersistenceError(f"Relationship {relationship_id} missing source/target")

        sql = """
        INSERT INTO relationships (relationship_id, source_id, source_type, target_id, target_type, relationship_type, timestamp, confidence, extraction_method, created_at, metadata)
        VALUES (%s, %s, %s::entity_type, %s, %s::entity_type, %s::relationship_type, %s::timestamptz, %s, %s, COALESCE(%s::timestamptz, NOW()), %s::jsonb)
        ON CONFLICT (relationship_id) DO UPDATE SET
            source_id = EXCLUDED.source_id,
            source_type = EXCLUDED.source_type,
            target_id = EXCLUDED.target_id,
            target_type = EXCLUDED.target_type,
            relationship_type = EXCLUDED.relationship_type,
            timestamp = EXCLUDED.timestamp,
            confidence = EXCLUDED.confidence,
            extraction_method = EXCLUDED.extraction_method,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING (xmax = 0) AS inserted
        """
        cur = self._execute(sql, (relationship_id, source_id, source_type, target_id, target_type, relationship_type, timestamp, confidence, extraction_method, created_at, metadata))
        inserted = cur.fetchone()[0]
        cur.close()
        return "inserted" if inserted else "updated"

    def save_case(self, case_id: str, payload: Dict[str, Any]) -> str:
        return self._upsert_case(case_id, payload)

    def save_evidence(self, evidence_id: str, payload: Dict[str, Any]) -> str:
        return self._upsert_evidence(evidence_id, payload)

    # -- reads --------------------------------------------------------------

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        entity_type = _infer_type_from_id(entity_id)
        if entity_type and entity_type in ENTITY_TABLE_MAP:
            table, pk = ENTITY_TABLE_MAP[entity_type]
            sql = f"SELECT * FROM {table} WHERE {pk} = %s"
            rows, cols = self._fetchall(sql, (entity_id,))
            if rows:
                return dict(zip(cols, rows))
        # Fallback: search all tables
        for etype, (table, pk) in ENTITY_TABLE_MAP.items():
            sql = f"SELECT * FROM {table} WHERE {pk} = %s"
            try:
                rows, cols = self._fetchall(sql, (entity_id,))
                if rows:
                    d = dict(zip(cols, rows))
                    d["entity_type"] = etype
                    d["entity_id"] = entity_id
                    return d
            except PersistenceError:
                continue
        return None

    def get_relationships(self, entity_id: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT relationship_id, source_id, source_type, target_id, target_type,
               relationship_type, timestamp, confidence, extraction_method, created_at, metadata
        FROM relationships
        WHERE source_id = %s OR target_id = %s
        ORDER BY created_at
        """
        rows, cols = self._fetchall(sql, (entity_id, entity_id))
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            # Convert timestamp to ISO Z
            if d.get("timestamp"):
                d["timestamp"] = d["timestamp"].isoformat().replace("+00:00", "Z") if hasattr(d["timestamp"], "isoformat") else str(d["timestamp"])
            if d.get("created_at"):
                d["created_at"] = d["created_at"].isoformat().replace("+00:00", "Z") if hasattr(d["created_at"], "isoformat") else str(d["created_at"])
            result.append(d)
        return result

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM cases WHERE case_id = %s"
        rows, cols = self._fetchall(sql, (case_id,))
        if rows:
            return dict(zip(cols, rows))
        return None

    def get_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM evidence WHERE evidence_id = %s"
        rows, cols = self._fetchall(sql, (evidence_id,))
        if rows:
            return dict(zip(cols, rows))
        return None

    # -- transactions -------------------------------------------------------

    @contextmanager
    def transaction(self):
        conn = self._connect()
        # Use explicit transaction
        orig_autocommit = getattr(conn, "autocommit", True)
        # psycopg3: autocommit false means transaction
        try:
            if hasattr(conn, "autocommit"):
                conn.autocommit = False  # type: ignore
            self._in_transaction = True
            yield self
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._in_transaction = False
            if hasattr(conn, "autocommit"):
                conn.autocommit = orig_autocommit  # type: ignore

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
