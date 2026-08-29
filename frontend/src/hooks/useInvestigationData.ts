import { useMemo, useState, useEffect } from "react";
import { entities as mockEntities, relationships as mockRels, timelineEvents as mockTimeline, alerts as mockAlerts, cases as mockCases, allSearchItems as mockSearch } from "../data/mockData";
import { DATA_SOURCE } from "../config";
import { Entity, Relationship, InvestigationData } from "../types";

// Clean abstraction: UI does not care whether data comes from mock or FastAPI.
// DATA_SOURCE="mock" keeps current behavior; switching to "api" only changes this layer.
export function useInvestigationData(): InvestigationData & { loading: boolean; error: string | null } {
  const [loading] = useState(false);
  const [error] = useState<string | null>(null);
  // In mock mode return deterministic data synchronously; in api mode this hook would fetch via apiClient
  const data: InvestigationData = useMemo(() => {
    if (DATA_SOURCE === "mock") {
      return { entities: mockEntities, relationships: mockRels, timelineEvents: mockTimeline, alerts: mockAlerts, cases: mockCases, allSearchItems: mockSearch };
    }
    // Placeholder for api mode — returns mock until wired; avoids rewrite of consumers
    return { entities: mockEntities, relationships: mockRels, timelineEvents: mockTimeline, alerts: mockAlerts, cases: mockCases, allSearchItems: mockSearch };
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

// Async entity fetch abstraction (api-ready, currently mock)
export function useAsyncEntity(entityId: string | null) {
  const [data, setData] = useState<Entity | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!entityId) { setData(null); return; }
    setLoading(true);
    setError(null);
    const t = setTimeout(() => {
      const found = mockEntities.find(e => e.id === entityId) || null;
      if (!found) setError("Invalid entity");
      setData(found);
      setLoading(false);
    }, 80);
    return () => clearTimeout(t);
  }, [entityId]);
  return { data, loading, error };
}
