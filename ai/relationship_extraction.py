"""Relationship extraction from entities and text.

Produces RelationshipSchema objects with full provenance so that the
canonical relationship model is consistently populated.

This is a rule-based STARTER implementation only. Real NER / ML-based
extraction is explicitly OUT OF SCOPE for this milestone.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .schemas import (
    CANONICAL_ENTITY_TYPES,
    EntitySchema,
    RelationshipSchema,
)

_REL_COUNTER = {"rel": 0}


def _next_rel_id() -> str:
    _REL_COUNTER["rel"] += 1
    return f"rel-{_REL_COUNTER['rel']:05d}"


def _as_dict(e: Any) -> Dict[str, Any]:
    """Accept either EntitySchema objects or plain dicts."""
    if isinstance(e, EntitySchema):
        return e.to_dict()
    return e


def _entity_id(e: Dict[str, Any]) -> str:
    return e.get("normalized_id") or f"{e.get('entity_type', 'x').lower()}-UNKNOWN"


def extract_relationships(
    entities: List[Any],
    text: str,
    source_id_map: Dict[str, str] | None = None,
) -> List[RelationshipSchema]:
    """Extract candidate relationships between extracted entities.

    Args:
        entities: EntitySchema objects or dicts with text/entity_type/start.
        text: Source text from which entities were extracted.
        source_id_map: Optional mapping entity text -> stable ID.

    Returns:
        Validated list of RelationshipSchema objects.
    """
    source_id_map = source_id_map or {}
    items = [_as_dict(e) for e in entities]
    relationships: List[RelationshipSchema] = []

    def _resolve(e: Dict[str, Any], fallback_prefix: str) -> str:
        mapped = source_id_map.get(e.get("text", ""))
        if mapped:
            return mapped
        eid = _entity_id(e)
        if eid.endswith("-UNKNOWN"):
            # Deterministic fallback ID for unresolved mentions
            return f"{fallback_prefix}-00000"
        return eid

    persons = [e for e in items if e.get("entity_type") == "Person"]
    phones = [e for e in items if e.get("entity_type") == "PhoneNumber"]
    orgs = [e for e in items if e.get("entity_type") == "Organization"]
    vehicles = [e for e in items if e.get("entity_type") == "Vehicle"]

    # 1. Person-Person KNOWS via co-occurrence
    for i, src in enumerate(persons):
        for tgt in persons[i + 1:i + 2]:
            relationships.append(RelationshipSchema(
                source_id=_resolve(src, "person"),
                source_type="Person",
                target_id=_resolve(tgt, "person"),
                target_type="Person",
                relationship_type="KNOWS",
                confidence=0.45,
                extraction_method="co_occurrence",
                relationship_id=_next_rel_id(),
                metadata={"text_excerpt": text[:120]},
            ))

    # 2. Person CALLED PhoneNumber via proximity
    for person in persons:
        for phone in phones:
            if person.get("start") is not None and phone.get("start") is not None \
                    and abs(phone["start"] - person["start"]) < 50:
                relationships.append(RelationshipSchema(
                    source_id=_resolve(person, "person"),
                    source_type="Person",
                    target_id=_resolve(phone, "phone"),
                    target_type="PhoneNumber",
                    relationship_type="CALLED",
                    confidence=0.6,
                    extraction_method="proximity",
                    relationship_id=_next_rel_id(),
                ))

    # 3. Person WORKS_FOR Organization via co-occurrence
    for person in persons:
        for org in orgs:
            relationships.append(RelationshipSchema(
                source_id=_resolve(person, "person"),
                source_type="Person",
                target_id=_resolve(org, "org"),
                target_type="Organization",
                relationship_type="WORKS_FOR",
                confidence=0.5,
                extraction_method="co_occurrence",
                relationship_id=_next_rel_id(),
            ))

    # 4. Person OWNS Vehicle via co-occurrence
    for person in persons:
        for vehicle in vehicles:
            relationships.append(RelationshipSchema(
                source_id=_resolve(person, "person"),
                source_type="Person",
                target_id=_resolve(vehicle, "vehicle"),
                target_type="Vehicle",
                relationship_type="OWNS",
                confidence=0.5,
                extraction_method="co_occurrence",
                relationship_id=_next_rel_id(),
            ))

    for rel in relationships:
        rel.validate()

    return relationships


if __name__ == "__main__":
    from .entity_extraction import extract_entities

    demo_text = (
        "Rhea Verma called +91-901234567 about Kabir Rao. "
        "Rhea Verma works with Bluepeak Traders Pvt Ltd."
    )
    ents = extract_entities(demo_text)
    phone_ents = [{
        "text": "+91-901234567",
        "entity_type": "PhoneNumber",
        "start": demo_text.find("+91-901234567"),
        "end": demo_text.find("+91-901234567") + 13,
        "normalized_id": "phone-00001",
    }]
    rels = extract_relationships(ents + phone_ents, demo_text)
    for r in rels:
        print(r.to_dict())
