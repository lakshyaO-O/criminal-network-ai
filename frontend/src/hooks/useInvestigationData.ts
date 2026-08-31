import { useMemo, useState, useEffect } from "react";
import { entities as mockEntities, relationships as mockRels, timelineEvents as mockTimeline, alerts as mockAlerts, cases as mockCases, allSearchItems as mockSearch } from "../data/mockData";
import { DATA_SOURCE } from "../config";
import { Entity, Relationship, InvestigationData } from "../types";

// Legacy hook — kept for compat but deprecated. In api mode it returns empty and an error hint so callers migrate to useNetworkData.
// Do not use for new code; App.tsx now uses useNetworkData (real API) as source of truth.
export function useInvestigationData(): InvestigationData & { loading: boolean; error: string | null } {
  const [loading] = useState(false);
  const [error] = useState<string | null>(DATA_SOURCE === "api" ? "useInvestigationData is deprecated in api mode — use useNetworkData" : null);
  const data: InvestigationData = useMemo(() => {
    if (DATA_SOURCE === "mock") {
      return { entities: mockEntities, relationships: mockRels, timelineEvents: mockTimeline, alerts: mockAlerts, cases: mockCases, allSearchItems: mockSearch };
    }
    // In api mode do not silently return mock — return empty so failures are visible (ErrorState/EmptyState)
    return { entities: [], relationships: [], timelineEvents: [], alerts: [], cases: [], allSearchItems: [] };
  }, []);
  return { ...data, loading, error };
}

export function useEntity(entityId: string | null): Entity | null {
  const { entities } = useInvestigationData();
  return useMemo(() => {
    if (!entityId) return null;
    return entities.find(e => e.id === entityId) || null;
  }, [entityId, entities]);
}

export function useNetwork(entityId: string | null) {
  const { entities, relationships } = useInvestigationData();
  return useMemo(() => {
    if (!entityId) return { nodes: entities, edges: relationships };
    const edgeIds = new Set<string>();
    const nodeIds = new Set<string>([entityId]);
    relationships.forEach(r => {
      if (r.source === entityId || r.target === entityId) {
        edgeIds.add(r.id);
        nodeIds.add(r.source);
        nodeIds.add(r.target);
      }
    });
    return {
      nodes: entities.filter(e => nodeIds.has(e.id)),
      edges: relationships.filter(r => edgeIds.has(r.id))
    };
  }, [entityId, entities, relationships]);
}

export function useRelationshipsForEntity(entityId: string | null): Relationship[] {
  const { relationships } = useInvestigationData();
  return useMemo(() => {
    if (!entityId) return [];
    return relationships.filter(r => r.source === entityId || r.target === entityId);
  }, [entityId, relationships]);
}

// Async entity fetch abstraction — mock only when explicit, otherwise delegates to real API via getEntity
export function useAsyncEntity(entityId: string | null) {
  const [data, setData] = useState<Entity | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!entityId) { setData(null); setError(null); return; }
    if (DATA_SOURCE === "mock") {
      setLoading(true); setError(null);
      const t = setTimeout(() => {
        const found = mockEntities.find(e => e.id === entityId) || null;
        if (!found) setError("Invalid entity");
        setData(found);
        setLoading(false);
      }, 80);
      return () => clearTimeout(t);
    }
    // api mode: fetch via real endpoint
    setLoading(true); setError(null); setData(null);
    import("../api/entities").then(m=> m.getEntity(entityId).then(o=> {
      setData({ id: o.entity_id, type: (o.entity_type as Entity["type"]) || "Person", displayName: String(o.full_name || o.name || o.entity_id), confidence: 0.85, relationshipCount: 0, sourceCount: 1, associatedCases: [], lastObserved: new Date().toISOString().slice(0,19).replace("T"," "), metadata: (o.metadata as Record<string,string>)||{}} as Entity);
      setLoading(false);
    }).catch(e=> { setError(e instanceof Error ? e.message : String(e)); setLoading(false); }));
  }, [entityId]);
  return { data, loading, error };
}
