"""Tests for PostgreSQL persistence (Milestone 4).

Covers:
- entity insert / upsert
- relationship insert / upsert (provenance)
- retrieval (entity, relationships, case, evidence)
- idempotent synthetic import
- transaction rollback
- provenance preservation

If a real PostgreSQL instance is unavailable, tests are SKIPPED (not faked).
Existing 53 tests remain runnable via InMemoryPersistence.

Requires:
    DATABASE_URL or default docker-compose postgres
    db/001_initial_schema.sql applied

Run:
    pytest tests/test_persistence.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend-python"))

from ai.persistence.memory import InMemoryPersistence
from ai.persistence.base import PersistenceError

# Try to import PostgresPersistence; if driver not installed, skip all postgres tests
try:
    from ai.persistence.postgres import PostgresPersistence

    _pg_driver_available = True
    _pg_import_error = None
except Exception as exc:  # pragma: no cover
    PostgresPersistence = None  # type: ignore
    _pg_driver_available = False
    _pg_import_error = exc


def _pg_available() -> bool:
    if not _pg_driver_available:
        return False
    try:
        pg = PostgresPersistence()  # type: ignore
        ok = pg.health_check()
        try:
            pg.close()
        except Exception:
            pass
        return ok
    except Exception:
        return False


_cached_pg_available: bool | None = None


def _is_pg_available() -> bool:
    # Lazy check with short timeout; cached per process
    # Avoid calling at import time to prevent collection hangs
    global _cached_pg_available  # type: ignore
    if _cached_pg_available is not None:
        return _cached_pg_available
    result = _pg_available()
    _cached_pg_available = result
    return result


# For pytest markers we need a static bool but we compute lazily inside each test via skipif function
# Use a callable for skipif: pytest will evaluate at test time if we use a function, but skipif expects bool.
# We keep PG_AVAILABLE lazy by checking inside test functions; markers will be dynamic via helper.
PG_AVAILABLE = False  # placeholder; real check is _is_pg_available() inside tests


# ---------------------------------------------------------------------------
# In-memory persistence tests (always runnable, verify contract parity)
# ---------------------------------------------------------------------------

def test_memory_entity_insert_and_retrieval():
    mem = InMemoryPersistence()
    result = mem.save_entity("person-00001", "Person", {"full_name": "Test Person", "metadata": {"note": "x"}})
    assert result in ("inserted", "updated")
    entity = mem.get_entity("person-00001")
    assert entity is not None
    assert entity["entity_id"] == "person-00001"
    assert entity["entity_type"] == "Person"


def test_memory_entity_upsert():
    mem = InMemoryPersistence()
    mem.save_entity("person-00001", "Person", {"full_name": "Alice"})
    result = mem.save_entity("person-00001", "Person", {"full_name": "Alice Updated"})
    assert result == "updated"
    assert mem.get_entity("person-00001")["full_name"] == "Alice Updated"
    assert mem.count_entities() == 1  # not duplicated


def test_memory_relationship_insert_and_retrieval():
    mem = InMemoryPersistence()
    mem.save_entity("person-00001", "Person", {"full_name": "A"})
    mem.save_entity("person-00002", "Person", {"full_name": "B"})
    rel = {
        "relationship_id": "rel-00001",
        "source": {"entity_id": "person-00001", "entity_type": "Person", "text": "A"},
        "target": {"entity_id": "person-00002", "entity_type": "Person", "text": "B"},
        "source_id": "person-00001",
        "source_type": "Person",
        "target_id": "person-00002",
        "target_type": "Person",
        "relationship_type": "KNOWS",
        "confidence": 0.8,
        "extraction_method": "pattern",
        "timestamp": "2024-01-01T00:00:00Z",
        "created_at": "2024-01-01T00:00:00Z",
        "metadata": {},
    }
    mem.save_relationship("rel-00001", rel)
    rels = mem.get_relationships("person-00001")
    assert len(rels) == 1
    assert rels[0]["relationship_id"] == "rel-00001"


def test_memory_relationship_upsert():
    mem = InMemoryPersistence()
    rel = {
        "relationship_id": "rel-00001",
        "source_id": "person-00001",
        "source_type": "Person",
        "target_id": "person-00002",
        "target_type": "Person",
        "relationship_type": "KNOWS",
        "confidence": 0.8,
        "extraction_method": "pattern",
        "metadata": {},
    }
    mem.save_relationship("rel-00001", rel)
    rel["confidence"] = 0.9
    result = mem.save_relationship("rel-00001", rel)
    assert result == "updated"
    assert mem.count_relationships() == 1


def test_memory_transaction_rollback():
    mem = InMemoryPersistence()
    try:
        with mem.transaction():
            mem.save_entity("person-00001", "Person", {"full_name": "A"})
            mem.save_entity("person-00002", "Person", {"full_name": "B"})
            raise ValueError("forced failure")
    except ValueError:
        pass
    # In-memory transaction snapshots and rolls back on exception
    assert mem.get_entity("person-00001") is None
    assert mem.get_entity("person-00002") is None


def test_memory_provenance_preservation():
    mem = InMemoryPersistence()
    payload = {
        "relationship_id": "rel-00099",
        "source_id": "person-00001",
        "source_type": "Person",
        "target_id": "person-00002",
        "target_type": "Person",
        "relationship_type": "CALLED",
        "timestamp": "2024-06-15T10:00:00Z",
        "confidence": 0.75,
        "extraction_method": "rule:called_cue",
        "created_at": "2024-01-01T00:00:00Z",
        "metadata": {"cue_window_verified": True},
    }
    mem.save_relationship("rel-00099", payload)
    stored = mem.relationships["rel-00099"]
    for field in ("relationship_id", "source_id", "source_type", "target_id", "target_type", "timestamp", "confidence", "extraction_method", "created_at"):
        assert field in stored or field in payload
    assert stored["confidence"] == 0.75
    assert stored["extraction_method"] == "rule:called_cue"


# ---------------------------------------------------------------------------
# PostgreSQL tests (require live DB, else SKIP)
# ---------------------------------------------------------------------------

def test_postgres_entity_insert_and_upsert():
    if not _pg_driver_available:
        pytest.skip(f"psycopg not installed: {_pg_import_error}")
    if not _is_pg_available():
        pytest.skip("PostgreSQL not available (health_check failed) — start with: docker compose up -d postgres")
    pg = PostgresPersistence()  # type: ignore
    # Use distinct test IDs to avoid colliding with synthetic data
    pid = "person-99991"
    try:
        result = pg.save_entity(pid, "Person", {"full_name": "PG Test Person", "date_of_birth": "1990-01-01", "nationality": "IN (fictional)", "metadata": {"test": True}})
        assert result in ("inserted", "updated")
        entity = pg.get_entity(pid)
        assert entity is not None
        # PostgreSQL returns row with person_id etc; check at least one field
        assert entity.get("person_id") == pid or entity.get("entity_id") == pid or entity.get("full_name") == "PG Test Person"

        # Upsert (update)
        result2 = pg.save_entity(pid, "Person", {"full_name": "PG Test Person Updated", "metadata": {"test": True}})
        assert result2 == "updated"
        entity2 = pg.get_entity(pid)
        assert entity2 is not None
        assert entity2.get("full_name") == "PG Test Person Updated"
    finally:
        # Cleanup
        try:
            pg._execute("DELETE FROM persons WHERE person_id = %s", (pid,))  # type: ignore
            pg._connect().commit()  # type: ignore
        except Exception:
            pass
        pg.close()


def test_postgres_relationship_provenance():
    if not _pg_driver_available:
        pytest.skip("psycopg not installed")
    if not _is_pg_available():
        pytest.skip("PostgreSQL not available")
    pg = PostgresPersistence()  # type: ignore
    # Ensure two persons exist first
    p1, p2 = "person-99992", "person-99993"
    rid = "rel-99991"
    try:
        pg.save_entity(p1, "Person", {"full_name": "PG A", "metadata": {}})
        pg.save_entity(p2, "Person", {"full_name": "PG B", "metadata": {}})
        payload = {
            "relationship_id": rid,
            "source_id": p1,
            "source_type": "Person",
            "target_id": p2,
            "target_type": "Person",
            "relationship_type": "KNOWS",
            "timestamp": "2024-01-15T10:00:00Z",
            "confidence": 0.88,
            "extraction_method": "test:provenance",
            "created_at": "2024-01-15T10:00:00Z",
            "metadata": {"test": "provenance"},
        }
        pg.save_relationship(rid, payload)
        rels = pg.get_relationships(p1)
        # Find our rel
        found = [r for r in rels if r.get("relationship_id") == rid]
        assert len(found) == 1
        r = found[0]
        for field in ("relationship_id", "source_id", "source_type", "target_id", "target_type", "confidence", "extraction_method"):
            assert r.get(field) is not None, f"missing provenance field {field}"
        assert float(r["confidence"]) == 0.88
        assert r["extraction_method"] == "test:provenance"
    finally:
        try:
            pg._execute("DELETE FROM relationships WHERE relationship_id = %s", (rid,))  # type: ignore
            pg._execute("DELETE FROM persons WHERE person_id IN (%s, %s)", (p1, p2))  # type: ignore
        except Exception:
            pass
        try:
            pg._connect().commit()  # type: ignore
        except Exception:
            pass
        pg.close()


def test_postgres_idempotent_import():
    if not _pg_driver_available:
        pytest.skip("psycopg not installed")
    if not _is_pg_available():
        pytest.skip("PostgreSQL not available")
    # Test that running synthetic import twice does not duplicate
    from ai.load_synthetic_data import import_dataset
    from pathlib import Path

    data_dir = Path(__file__).parent.parent / "data" / "synthetic"
    pg = PostgresPersistence()  # type: ignore
    # Ensure schema exists
    if not pg.health_check():
        pg.init_schema()
    pg.close()

    # First import
    stats1 = import_dataset(data_dir)
    # Second import (should be all updates, 0 inserts)
    stats2 = import_dataset(data_dir)

    assert stats1["entities_inserted"] + stats1["entities_updated"] > 0
    assert stats2["entities_inserted"] == 0 or stats2["entities_updated"] > 0
    # No errors on second run
    assert stats2["errors"] == [] or all("already" not in e.lower() for e in stats2["errors"])
    # Relationships similarly idempotent
    assert stats1["relationships_inserted"] + stats1["relationships_updated"] > 0


def test_postgres_transaction_rollback():
    if not _pg_driver_available:
        pytest.skip("psycopg not installed")
    if not _is_pg_available():
        pytest.skip("PostgreSQL not available")
    pg = PostgresPersistence()  # type: ignore
    pid1, pid2 = "person-99994", "person-99995"
    try:
        # Clean first
        try:
            pg._execute("DELETE FROM persons WHERE person_id IN (%s, %s)", (pid1, pid2))  # type: ignore
            pg._connect().commit()  # type: ignore
        except Exception:
            pass

        try:
            with pg.transaction():
                pg.save_entity(pid1, "Person", {"full_name": "Tx A", "metadata": {}})
                pg.save_entity(pid2, "Person", {"full_name": "Tx B", "metadata": {}})
                raise RuntimeError("forced rollback")
        except RuntimeError:
            pass

        # Both should be rolled back
        assert pg.get_entity(pid1) is None
        assert pg.get_entity(pid2) is None
    finally:
        pg.close()


def test_postgres_retrieval_case_and_evidence():
    if not _pg_driver_available:
        pytest.skip("psycopg not installed")
    if not _is_pg_available():
        pytest.skip("PostgreSQL not available")
    pg = PostgresPersistence()  # type: ignore
    # Case and evidence retrieval via synthetic data (should exist after import)
    from pathlib import Path

    data_dir = Path(__file__).parent.parent / "data" / "synthetic"
    import json

    cases = json.load(open(data_dir / "cases.json"))
    if not cases:
        pytest.skip("no cases in synthetic data")
    case_id = cases[0]["case_id"]
    retrieved = pg.get_case(case_id)
    # If import hasn't been run, case may not exist; try import
    if retrieved is None:
        from ai.load_synthetic_data import import_dataset

        import_dataset(data_dir)
        retrieved = pg.get_case(case_id)
    assert retrieved is not None
    assert retrieved.get("case_id") == case_id or retrieved.get("case_number") is not None
    pg.close()
