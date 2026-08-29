import { useEffect, useState, useRef } from "react";
import { DATA_SOURCE } from "../config";
import { getAnalysis, getBridges, getCentrality, getCommunities, getIndicators, getRelationshipStrength, getTemporal, getTransactionChains, getEntityAnalysis } from "../api/analysis";
import { getInvestigationPaths } from "../api/investigations";
import type { AnalysisResponse } from "../types";

export function useAnalysis(caseId?: string | null) {
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => {
    if (DATA_SOURCE === "mock") { setData(null); setError(null); setLoading(false); return; }
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true); setError(null); setData(null);
    getAnalysis(caseId || undefined).then(d=> { if(!ctrl.signal.aborted) setData(d); }).catch(e=> { if(!ctrl.signal.aborted) setError(e instanceof Error ? e.message : String(e)); }).finally(()=> { if(!ctrl.signal.aborted) setLoading(false); });
    return () => ctrl.abort();
  }, [caseId]);
  return { data, loading, error };
}

export function useGraphIntelligence(caseId?: string | null) {
  const [centrality, setCentrality] = useState<Awaited<ReturnType<typeof getCentrality>> | null>(null);
  const [communities, setCommunities] = useState<Awaited<ReturnType<typeof getCommunities>> | null>(null);
  const [bridges, setBridges] = useState<Awaited<ReturnType<typeof getBridges>> | null>(null);
  const [temporal, setTemporal] = useState<Awaited<ReturnType<typeof getTemporal>> | null>(null);
  const [chains, setChains] = useState<Awaited<ReturnType<typeof getTransactionChains>> | null>(null);
  const [strength, setStrength] = useState<Awaited<ReturnType<typeof getRelationshipStrength>> | null>(null);
  const [indicators, setIndicators] = useState<Awaited<ReturnType<typeof getIndicators>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);

  useEffect(() => {
    if (DATA_SOURCE === "mock") {
      setCentrality(null); setCommunities(null); setBridges(null); setTemporal(null); setChains(null); setStrength(null); setIndicators(null); setError(null); setLoading(false);
      return;
    }
    const seq = ++seqRef.current;
    setLoading(true); setError(null);
    setCentrality(null); setCommunities(null); setBridges(null); setTemporal(null); setChains(null); setStrength(null); setIndicators(null);
    Promise.all([getCentrality(), getCommunities(), getBridges(), getTemporal(), getTransactionChains(), getRelationshipStrength(), getIndicators()])
      .then(([c, com, b, t, ch, s, ind]) => {
        if (seq !== seqRef.current) return;
        setCentrality(c); setCommunities(com); setBridges(b); setTemporal(t); setChains(ch); setStrength(s); setIndicators(ind);
      })
      .catch(e=> { if (seq === seqRef.current) setError(e instanceof Error ? e.message : String(e)); })
      .finally(()=> { if (seq === seqRef.current) setLoading(false); });
  }, [caseId]);

  return { centrality, communities, bridges, temporal, chains, strength, indicators, loading, error };
}

export function useEntityIntelligence(entityId: string | null) {
  const [data, setData] = useState<Awaited<ReturnType<typeof getEntityAnalysis>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => {
    if (!entityId || DATA_SOURCE==="mock") { setData(null); setError(null); setLoading(false); return; }
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true); setError(null); setData(null);
    getEntityAnalysis(entityId).then(d=> { if(!ctrl.signal.aborted) setData(d); }).catch(e=> { if(!ctrl.signal.aborted) setError(e instanceof Error ? e.message : String(e)); }).finally(()=> { if(!ctrl.signal.aborted) setLoading(false); });
    return () => ctrl.abort();
  }, [entityId]);
  return { data, loading, error };
}

export function usePath(source: string | null, target: string | null, caseId?: string | null) {
  const [data, setData] = useState<Awaited<ReturnType<typeof getInvestigationPaths>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!source || !target || DATA_SOURCE==="mock") { setData(null); setError(null); setLoading(false); return; }
    setLoading(true); setError(null); setData(null);
    getInvestigationPaths({ source_id: source, target_id: target, max_depth: 6, case_id: caseId ?? undefined }).then(d=> setData(d)).catch(e=> setError(e instanceof Error ? e.message : String(e))).finally(()=> setLoading(false));
  }, [source, target, caseId]);
  return { data, loading, error };
}
