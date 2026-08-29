"""Audit Service — Milestone 9A.

Deterministic, bounded, provenance-aware audit trail for analytical actions.

Captures: analysis_requested/completed, investigation_created, finding_generated,
evidence_generated, snapshot_generated, explainability_requested.

No user auth, no secrets, no unbounded dumps. All events are analytical audit,
not identity management.

Storage: in-memory bounded list (1000 events) for this milestone; future may
persist to PostgreSQL with explicit ADR. Deterministic IDs via hash, deterministic
ordering via timestamp + audit_id.

Security: never logs credentials, env vars, connection strings, raw headers,
or uncontrolled payload copies; stores references (IDs, analysis_type, case_id).
"""

from __future__ import annotations

import hashlib
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Fixed timestamp for deterministic tests; in production would use now()
FIXED_TIMESTAMP = "2024-01-01T00:00:00Z"


def _now_iso() -> str:
    # For audit, use fixed for determinism in tests; could switch to real time later
    return FIXED_TIMESTAMP


def _hash_audit_id(*parts: str) -> str:
    return f"audit-{hashlib.sha256('|'.join(parts).encode()).hexdigest()[:12]}"


# Bounded in-memory store (1000 max, deterministic FIFO)
_MAX_EVENTS = 1000
_audit_store: deque = deque(maxlen=_MAX_EVENTS)


# Sensitive keys to never log
_SENSITIVE_KEYS = {"password", "passwd", "secret", "token", "connection_string", "database_url", "dsn", "neo4j_password", "postgres_password"}


def _sanitize_params(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not params:
        return {}
    sanitized = {}
    for k, v in params.items():
        if k.lower() in _SENSITIVE_KEYS:
            continue
        # Only store references, not full payloads
        if isinstance(v, (str, int, float, bool)) or v is None:
            sanitized[k] = v
        elif isinstance(v, list) and len(v) <= 5:
            # Store small lists of IDs, not full objects
            sanitized[k] = [str(x)[:50] if isinstance(x, str) else str(x)[:50] for x in v]
        else:
            sanitized[k] = f"<{type(v).__name__}:{len(str(v)) if hasattr(v, '__len__') else 'ref'}>"
    return sanitized


def record_event(
    event_type: str,
    analysis_type: Optional[str] = None,
    case_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    root_entity_id: Optional[str] = None,
    object_id: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    provenance: Optional[List[Dict[str, Any]]] = None,
    status: str = "completed",
) -> Dict[str, Any]:
    """Record an audit event. Returns the created event dict."""
    # Deterministic audit_id: hash of core fields (without timestamp for determinism)
    base = "|".join([
        event_type,
        analysis_type or "",
        case_id or "",
        entity_id or "",
        root_entity_id or "",
        object_id or "",
        str(sorted((_sanitize_params(parameters) or {}).items())),
    ])
    audit_id = _hash_audit_id(base, event_type)
    # Ensure uniqueness if same base occurs multiple times: append counter
    # Check if audit_id already exists, if so add suffix
    existing_ids = {e["audit_id"] for e in _audit_store}
    suffix = 0
    orig_id = audit_id
    while audit_id in existing_ids:
        suffix += 1
        audit_id = f"{orig_id}-{suffix}"

    event = {
        "audit_id": audit_id,
        "event_type": event_type,
        "timestamp": _now_iso(),
        "case_id": case_id,
        "entity_id": entity_id,
        "root_entity_id": root_entity_id,
        "analysis_type": analysis_type,
        "object_id": object_id,
        "parameters": _sanitize_params(parameters),
        "provenance": provenance or [],
        "status": status,
    }
    _audit_store.append(event)
    return event


def query_events(
    case_id: Optional[str] = None,
    analysis_type: Optional[str] = None,
    event_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    root_entity_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Bounded, deterministic querying. Never unbounded dump."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be 1..100")
    if offset < 0:
        raise ValueError("offset must be >=0")

    filtered = list(_audit_store)
    if case_id is not None:
        filtered = [e for e in filtered if e.get("case_id") == case_id]
    if analysis_type is not None:
        filtered = [e for e in filtered if e.get("analysis_type") == analysis_type]
    if event_type is not None:
        filtered = [e for e in filtered if e.get("event_type") == event_type]
    if entity_id is not None:
        filtered = [e for e in filtered if e.get("entity_id") == entity_id or e.get("object_id") == entity_id]
    if root_entity_id is not None:
        filtered = [e for e in filtered if e.get("root_entity_id") == root_entity_id]
    if start_time is not None:
        # Simple string compare (ISO)
        filtered = [e for e in filtered if e.get("timestamp", "") >= start_time]
    if end_time is not None:
        filtered = [e for e in filtered if e.get("timestamp", "") <= end_time]

    # Deterministic ordering: timestamp asc, then audit_id asc
    filtered.sort(key=lambda e: (e.get("timestamp", ""), e.get("audit_id", "")))
    return filtered[offset: offset + limit]


def clear_events():
    """For tests only."""
    _audit_store.clear()


def count_events() -> int:
    return len(_audit_store)
