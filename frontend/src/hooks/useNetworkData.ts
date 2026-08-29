import { useEffect, useState, useMemo, useRef } from "react";
import { DATA_SOURCE } from "../config";
import { getNetwork } from "../api/networks";
import { getEntity, getEntityRelationships } from "../api/entities";
import { entities as mockEntities, relationships as mockRels, timelineEvents as mockTimeline, alerts as mockAlerts, cases as mockCases } from "../data/mockData";
import type { Entity, Relationship, TimelineEvent, Alert, CaseItem } from "../types";
import { canonicalToDisplay } from "../types";
import { ApiError } from "../api/client";

function mapEntityOutToEntity(o: { entity_id: string; entity_type: string; full_name?: string | null; name?: string | null; metadata?: Record<string, unknown> }): Entity {
  const displayType = canonicalToDisplay[o.entity_type] || "Person";
  const name = (o.full_name as string) || (o.name as string) || o.entity_id;
  return {
    id: o.entity_id,
    type: displayType,
    canonicalType: o.entity_type as Entity["canonicalType"],
    displayName: String(name),
    confidence: 0.85,
    relationshipCount: 0,
    sourceCount: 1,
    associatedCases: [],
    lastObserved: (o.metadata as Record<string, string>)?.last_observed || new Date().toISOString().slice(0, 19).replace("T", " "),
    metadata: (o.metadata as Record<string, string>) || {}
  };
}

function mapRelationshipOut(r: { relationship_id: string; source: Record<string, unknown>; target: Record<string, unknown>; relationship_type: string; confidence: number; timestamp?: string | null; source_id?: string | null; extraction_method?: string }): Relationship {
  return {
    id: r.relationship_id,
    source: String((r.source as Record<string, string>).entity_id || ""),
    target: String((r.target as Record<string, string>).entity_id || ""),
    type: r.relationship_type as Relationship["type"],
    confidence: r.confidence,
    timestamp: r.timestamp ?? null,
    sourceId: String(r.source_id || r.relationship_id),
    extractionMethod: r.extraction_method,
    metadata: {}
  };
}

export function useNetworkData(caseId: string | null) {
  const [entities, setEntities] = useState<Entity[]>(DATA_SOURCE==="mock" ? mockEntities : []);
  const [relationships, setRelationships] = useState<Relationship[]>(DATA_SOURCE==="mock" ? mockRels : []);
  const [cases, setCases] = useState<CaseItem[]>(mockCases);
  const [timelineEvents] = useState<TimelineEvent[]>(mockTimeline);
  const [alerts] = useState<Alert[]>(mockAlerts);
  const [loading, setLoading] = useState(DATA_SOURCE==="api");
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const seqRef = useRef(0);

  useEffect(() => {
    if (DATA_SOURCE === "mock" || !caseId) {
      if (DATA_SOURCE === "mock") {
        setEntities(mockEntities); setRelationships(mockRels); setCases(mockCases); setError(null); setLoading(false);
      }
      return;
    }
    const seq = ++seqRef.current;
    setLoading(true); setError(null);
    // do not clear entities immediately to avoid flicker — but clear stale error
    getNetwork(caseId).then(net => {
      if (seq !== seqRef.current) return;
      const mappedEntities = net.entities.map(e => mapEntityOutToEntity(e as unknown as { entity_id: string; entity_type: string; full_name?: string | null; name?: string | null; metadata?: Record<string, unknown> }));
      const mappedRels = net.relationships.map(r => mapRelationshipOut(r as unknown as { relationship_id: string; source: Record<string, unknown>; target: Record<string, unknown>; relationship_type: string; confidence: number; timestamp?: string | null; source_id?: string | null; extraction_method?: string }));
      const countMap = new Map<string, number>();
      mappedRels.forEach(r => { countMap.set(r.source, (countMap.get(r.source)||0)+1); countMap.set(r.target, (countMap.get(r.target)||0)+1); });
      const enriched = mappedEntities.map(e => ({ ...e, relationshipCount: countMap.get(e.id) || 0, associatedCases: [caseId] }));
      setEntities(enriched);
      setRelationships(mappedRels);
      import("../api/cases").then(m => m.getCase(caseId).then(c => {
        if (seq !== seqRef.current) return;
        setCases(prev => {
          const exists = prev.find(x=>x.id===c.case_id);
          const mapped: CaseItem = { id: c.case_id, number: c.case_number, title: c.title, status: c.status as CaseItem["status"], entityCount: mappedEntities.length, description: c.description, case_type: c.case_type };
          if (exists) return prev.map(x=> x.id===c.case_id?mapped:x);
          return [...prev, mapped];
        });
      }).catch(()=>{ /* keep cases as is */ }));
    }).catch((e: unknown) => {
      if (seq !== seqRef.current) return;
      const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e);
      setError(msg);
      setEntities([]); setRelationships([]);
    }).finally(()=> { if (seq === seqRef.current) setLoading(false); });
  }, [caseId, retryKey]);

  const allSearchItems = useMemo(() => [
    ...entities.map(e => ({ id: e.id, label: `${e.id} — ${e.displayName}`, type: e.type })),
    ...cases.map(c => ({ id: c.id, label: `${c.id} — ${c.title}`, type: "Case" as const })),
    ...relationships.map(r => ({ id: r.id, label: `${r.id} ${r.type}`, type: "Relationship" as const }))
  ], [entities, cases, relationships]);

  return { entities, relationships, timelineEvents, alerts, cases, allSearchItems, loading, error, retry: () => setRetryKey(k=>k+1) };
}

export function useEntityDetail(entityId: string | null) {
  const [data, setData] = useState<Entity | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (!entityId) { setData(null); setError(null); return; }
    if (DATA_SOURCE === "mock") {
      const m = mockEntities.find(e=>e.id===entityId) || null;
      setData(m); setError(m?null:"Invalid entity"); setLoading(false); return;
    }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setData(null);
    getEntity(entityId).then(o => {
      if (seq !== seqRef.current) return;
      setData(mapEntityOutToEntity(o as unknown as { entity_id: string; entity_type: string; full_name?: string | null; name?: string | null; metadata?: Record<string, unknown> }));
    }).catch((e: unknown)=> { if (seq===seqRef.current) setError(e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [entityId]);
  return { data, loading, error };
}

export function useEntityRelationships(entityId: string | null) {
  const [rels, setRels] = useState<Relationship[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (!entityId) { setRels([]); setError(null); return; }
    if (DATA_SOURCE === "mock") {
      setRels(mockRels.filter(r=>r.source===entityId||r.target===entityId)); setError(null); return;
    }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setRels([]);
    getEntityRelationships(entityId).then(out => {
      if (seq !== seqRef.current) return;
      setRels(out.relationships.map(r=> mapRelationshipOut(r as unknown as { relationship_id: string; source: Record<string, unknown>; target: Record<string, unknown>; relationship_type: string; confidence: number; timestamp?: string | null; source_id?: string | null; extraction_method?: string })));
    }).catch(e=> { if(seq===seqRef.current) setError(e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [entityId]);
  return { data: rels, loading, error };
}
