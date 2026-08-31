import { useEffect, useState, useRef } from "react";
import { DATA_SOURCE } from "../config";
import type { ExplanationResponse } from "../types";
import { getFindingExplanation, getEntityExplanation, getEntityCentralityExplanation, getBridgeExplanation, getTemporalExplanation, getCommunitiesExplanation } from "../api/explainability";
import { ApiError } from "../api/client";

export function useFindingExplanation(findingId: string | null) {
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (!findingId) { setData(null); setError(null); return; }
    if (DATA_SOURCE==="mock") { setData(null); setError("Explainability unavailable in mock mode"); return; }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setData(null);
    getFindingExplanation(findingId).then(d=> { if(seq===seqRef.current) setData(d); }).catch(e=> { if(seq===seqRef.current) setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [findingId]);
  return { data, loading, error };
}

export function useEntityExplanation(entityId: string | null) {
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (!entityId) { setData(null); setError(null); return; }
    if (DATA_SOURCE==="mock") { setData(null); setError("Explainability unavailable in mock mode"); return; }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setData(null);
    getEntityExplanation(entityId).then(d=> { if(seq===seqRef.current) setData(d); }).catch(e=> { if(seq===seqRef.current) setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [entityId]);
  return { data, loading, error };
}

export function useBridgeExplanation(entityId: string | null) {
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (!entityId || DATA_SOURCE==="mock") { setData(null); setError(entityId && DATA_SOURCE==="mock" ? "Explainability unavailable in mock mode" : null); return; }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setData(null);
    getBridgeExplanation(entityId).then(d=> { if(seq===seqRef.current) setData(d); }).catch(e=> { if(seq===seqRef.current) setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [entityId]);
  return { data, loading, error };
}

export function useTemporalExplanation(entityId: string | null) {
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (DATA_SOURCE==="mock") { setData(null); setError("Explainability unavailable in mock mode"); return; }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setData(null);
    getTemporalExplanation(entityId).then(d=> { if(seq===seqRef.current) setData(d); }).catch(e=> { if(seq===seqRef.current) setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [entityId]);
  return { data, loading, error };
}

export function useCommunitiesExplanation(entityId: string | null) {
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (DATA_SOURCE==="mock") { setData(null); setError("Explainability unavailable in mock mode"); return; }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setData(null);
    getCommunitiesExplanation(entityId).then(d=> { if(seq===seqRef.current) setData(d); }).catch(e=> { if(seq===seqRef.current) setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [entityId]);
  return { data, loading, error };
}

export function useCentralityExplanation(entityId: string | null) {
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (!entityId || DATA_SOURCE==="mock") { setData(null); setError(entityId && DATA_SOURCE==="mock" ? "Explainability unavailable in mock mode" : null); return; }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setData(null);
    getEntityCentralityExplanation(entityId).then(d=> { if(seq===seqRef.current) setData(d); }).catch(e=> { if(seq===seqRef.current) setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [entityId]);
  return { data, loading, error };
}

// Legacy hook used by analysis panels -- now requires entityId, kept for compat with disabled state
export function usePathExplanation(source: string | null, target: string | null) {
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [loading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (DATA_SOURCE==="mock") { setData(null); setError("Explainability unavailable in mock mode"); return; }
    if (!source || !target) { setData(null); setError(null); return; }
    setError("Path explainability not available for direct path -- use findings/temporal/bridge");
  }, [source, target]);
  return { data, loading, error };
}
