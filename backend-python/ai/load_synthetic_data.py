"""Synthetic data import — idempotent loader for PostgreSQL.

Usage:
    python -m ai.load_synthetic_data
    python -m ai.load_synthetic_data --reset          # drop & re-init schema (explicit only)
    python -m ai.load_synthetic_data --data-dir data/synthetic --dsn postgresql://...

Validates data, then upserts:
    entities inserted/updated
    relationships inserted/updated
    errors

Idempotent: running twice does NOT duplicate records (ON CONFLICT DO UPDATE).

Example:
    DATABASE_URL=postgresql://investigator:secure_password@localhost:5432/criminal_network python -m ai.load_synthetic_data
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from ai.schemas import RelationshipSchema, SchemaValidationError


def _load_dataset(data_dir: Path) -> Dict[str, Any]:
    dataset: Dict[str, Any] = {}
    for json_file in data_dir.glob("*.json"):
        if json_file.name.startswith("_"):
            continue
        with json_file.open(encoding="utf-8") as f:
            dataset[json_file.stem] = json.load(f)
    # Also load _generation_config if present (not needed for import, but preserve)
    cfg_path = data_dir / "_generation_config.json"
    if cfg_path.exists():
        with cfg_path.open(encoding="utf-8") as f:
            dataset["_generation_config"] = json.load(f)
    return dataset


def _validate_relationship(rel: Dict[str, Any]) -> None:
    # Use canonical schema for validation
    try:
        RelationshipSchema(
            relationship_id=rel["relationship_id"],
            source_id=rel["source_id"],
            source_type=rel["source_type"],
            target_id=rel["target_id"],
            target_type=rel["target_type"],
            relationship_type=rel["relationship_type"],
            confidence=float(rel["confidence"]),
            extraction_method=rel["extraction_method"],
            created_at=rel.get("created_at", "2024-01-01T00:00:00Z"),
            timestamp=rel.get("timestamp"),
            metadata=rel.get("metadata", {}),
        ).validate()
    except (KeyError, SchemaValidationError, ValueError) as exc:
        raise ValueError(f"relationship {rel.get('relationship_id')} invalid: {exc}") from exc


def import_dataset(data_dir: Path, dsn: str | None = None, reset: bool = False) -> Dict[str, Any]:
    """Import synthetic dataset into PostgreSQL. Returns stats dict."""
    from ai.persistence.postgres import PostgresPersistence

    persistence = PostgresPersistence(dsn=dsn)

    if reset:
        # Explicit reset requested: drop and re-init schema
        # We do not silently destroy; user must pass --reset
        print("Reset requested: re-initializing schema...")
        persistence.init_schema()

    # Ensure schema exists (idempotent — CREATE IF NOT EXISTS semantics in SQL)
    if not persistence.health_check():
        print("Schema not present, initializing...")
        persistence.init_schema()
        if not persistence.health_check():
            raise RuntimeError("Failed to initialize schema; health check failed after init")

    dataset = _load_dataset(data_dir)

    stats = {
        "entities_inserted": 0,
        "entities_updated": 0,
        "relationships_inserted": 0,
        "relationships_updated": 0,
        "errors": [],
    }

    # Map dataset keys to entity handling
    # Each collection corresponds to an entity type; we preserve IDs and provenance
    entity_keys = [
        "persons",
        "organizations",
        "phone_numbers",
        "vehicles",
        "locations",
        "financial_accounts",
        "transactions",
        "communications",
        "cases",
        "firs",
        "events",
        "evidence",
    ]

    # Use transaction for atomicity per collection? Use one big transaction for all
    try:
        with persistence.transaction():
            for key in entity_keys:
                rows = dataset.get(key, [])
                for row in rows:
                    try:
                        entity_id = row.get("entity_id") or row.get(f"{key[:-1]}_id") or row.get(f"{key.rstrip('s')}_id")
                        # For 'evidence' key, entity_id is evidence_id etc., but we handle fallback via prefix map
                        entity_type = row.get("entity_type")
                        if not entity_id or not entity_type:
                            # Try to infer from key
                            fallback_type = {
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
                            }.get(key)
                            entity_type = entity_type or fallback_type
                            entity_id = entity_id or row.get("entity_id")
                        if not entity_id or not entity_type:
                            stats["errors"].append(f"{key}: missing entity_id/type in {row}")
                            continue
                        result = persistence.save_entity(entity_id, entity_type, row)
                        if result == "inserted":
                            stats["entities_inserted"] += 1
                        else:
                            stats["entities_updated"] += 1
                    except Exception as exc:
                        stats["errors"].append(f"{key}/{row.get('entity_id')}: {exc}")

            # Relationships (must come after entities for FKs where possible)
            rels = dataset.get("relationships", [])
            for rel in rels:
                try:
                    _validate_relationship(rel)
                    result = persistence.save_relationship(rel["relationship_id"], rel)
                    if result == "inserted":
                        stats["relationships_inserted"] += 1
                    else:
                        stats["relationships_updated"] += 1
                except Exception as exc:
                    stats["errors"].append(f"relationship {rel.get('relationship_id')}: {exc}")

        # If we reach here, transaction committed
    except Exception as exc:
        # Transaction already rolled back via context manager
        stats["errors"].append(f"transaction failed: {exc}")
        raise

    return stats


def main():
    parser = argparse.ArgumentParser(description="Idempotent synthetic data loader for PostgreSQL")
    parser.add_argument("--data-dir", type=str, default="data/synthetic", help="Path to synthetic JSON directory")
    parser.add_argument("--dsn", type=str, default=None, help="PostgreSQL DSN (or DATABASE_URL env)")
    parser.add_argument("--reset", action="store_true", help="Drop and re-create schema before import (explicit)")
    parser.add_argument("--json", action="store_true", help="Output stats as JSON")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        stats = import_dataset(data_dir, dsn=args.dsn, reset=args.reset)
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print(f"Entities inserted: {stats['entities_inserted']}")
            print(f"Entities updated: {stats['entities_updated']}")
            print(f"Relationships inserted: {stats['relationships_inserted']}")
            print(f"Relationships updated: {stats['relationships_updated']}")
            if stats["errors"]:
                print(f"Errors: {len(stats['errors'])}")
                for err in stats["errors"][:10]:
                    print(f"  - {err}")
                if len(stats["errors"]) > 10:
                    print(f"  ... and {len(stats['errors']) - 10} more")
            else:
                print("No errors. Import idempotent: re-running will report 0 inserted, N updated.")
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
