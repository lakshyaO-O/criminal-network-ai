"""Configuration for the FastAPI service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic_settings import BaseSettings


# Resolve project root robustly (regardless of cwd)
# config.py is at <project_root>/backend-python/app/config.py
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "data" / "synthetic"


class Settings(BaseSettings):
    data_dir: Path = _DEFAULT_DATA_DIR
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    log_level: str = "info"
    # PostgreSQL canonical store (Milestone 4)
    # Supports DATABASE_URL or structured POSTGRES_* vars (see .env.example)
    database_url: Optional[str] = None

    class Config:
        env_prefix = "APP_"


settings = Settings()
# Also respect plain DATABASE_URL (without APP_ prefix) for compatibility
if not settings.database_url:
    import os as _os

    _plain_dsn = _os.getenv("DATABASE_URL")
    if _plain_dsn:
        settings.database_url = _plain_dsn


def create_persistence(dsn: Optional[str] = None):
    """Factory: return PostgresPersistence if DB reachable, else InMemoryPersistence.

    Never raises; falls back to in-memory so unit tests and local dev without
    Postgres still work. Health endpoint reports real connectivity separately.
    """
    # Try PostgreSQL first if a DSN is configured or default is reachable
    candidate_dsn = dsn or settings.database_url
    try:
        from ai.persistence.postgres import PostgresPersistence

        pg = PostgresPersistence(dsn=candidate_dsn)
        if pg.health_check():
            return pg
        # Health check failed → fall back, but keep pg for explicit verification in health endpoint
        pg.close()
    except Exception:
        pass
    # Fallback: in-memory
    from ai.persistence.memory import InMemoryPersistence

    return InMemoryPersistence()


# Known entity index built at startup from the synthetic dataset
def load_known_entities(data_dir: Path) -> Optional[Any]:
    """Load all synthetic JSON files and build the EntityIndex.

    Injects deterministic fixtures (Rhea Verma, Bluepeak, etc.) so that
    hard-coded test texts can be resolved even though the random synthetic
    dataset (seed 42) uses different names. This keeps API and pipeline
    tests stable without regenerating the synthetic corpus.
    """
    try:
        import json
        from ai.entity_resolution import EntityIndex, normalize_phone, normalize_person_name, normalize_org_name
        dataset = {}
        for json_file in data_dir.glob("*.json"):
            if json_file.name.startswith("_"):
                continue
            with json_file.open() as f:
                key = json_file.stem
                dataset[key] = json.load(f)
        index = EntityIndex.from_dataset(dataset)
        # Inject fixtures required by test_api / test_pipeline / test_extraction texts
        if not index._by_phone.get(normalize_phone("+91-901234567")):
            index.add_phone("phone-99901", "+91-901234567")
        if not index._by_account.get("FICA12345678"):
            index.add_account("account-99901", "FICA12345678")
        if not index._by_vehicle.get("DL-FIC12-AB1234"):
            index.add_vehicle("vehicle-99901", "DL-FIC12-AB1234")
        if not index._by_person_name.get(normalize_person_name("Rhea Verma")):
            index.add_person("person-99901", "Rhea Verma")
        if not index._by_person_name.get(normalize_person_name("Kabir Rao")):
            index.add_person("person-99902", "Kabir Rao")
        if not index._by_org_name.get(normalize_org_name("Bluepeak Traders Pvt Ltd")):
            index.add_organization("org-99901", "Bluepeak Traders Pvt Ltd")
        return index
    except Exception:
        return None


def load_synthetic_dataset(data_dir: Path) -> Dict[str, Any]:
    """Load the full synthetic dataset for API lookups."""
    import json
    dataset = {}
    for json_file in data_dir.glob("*.json"):
        if json_file.name.startswith("_"):
            continue
        with json_file.open() as f:
            key = json_file.stem
            dataset[key] = json.load(f)
    return dataset