import { useEffect, useState, useRef } from "react";
import { DATA_SOURCE } from "../config";
import type { ExplanationResponse } from "../types";
import { getFindingExplanation, getEntityExplanation, getPathExplanation, getCentralityExplanation } from "../api/explainability";
import { ApiError } from "../api/client";

export function useFindingExplanation(findingId: string | null, caseId?: string | null, rootId?: string | null) {
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (!findingId || DATA_SOURCE==="mock") { setData(null); setError(DATA_SOURCE==="mock" ? "Explainability unavailable in mock mode" : null); return; }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setData(null);
    getFindingExplanation(findingId, caseId ?? null, rootId ?? null).then(d=> { if(seq===seqRef.current) setData(d); }).catch(e=> { if(seq===seqRef.current) setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [findingId, caseId, rootId]);
  return { data, loading, error };
}

export function useEntityExplanation(entityId: string | null) {
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (!entityId || DATA_SOURCE==="mock") { setData(null); setError(DATA_SOURCE==="mock" ? "Explainability unavailable in mock mode" : null); return; }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setData(null);
    getEntityExplanation(entityId).then(d=> { if(seq===seqRef.current) setData(d); }).catch(e=> { if(seq===seqRef.current) setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [entityId]);
  return { data, loading, error };
}

export function usePathExplanation(source: string | null, target: string | null, caseId?: string | null) {
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (!source || !target || DATA_SOURCE==="mock") { setData(null); return; }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setData(null);
    getPathExplanation(source, target, caseId ?? null).then(d=> { if(seq===seqRef.current) setData(d); }).catch(e=> { if(seq===seqRef.current) setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [source, target, caseId]);
  return { data, loading, error };
}

export function useCentralityExplanation(enabled: boolean) {
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  useEffect(() => {
    if (!enabled || DATA_SOURCE==="mock") { setData(null); return; }
    const seq = ++seqRef.current;
    setLoading(true);
    getCentralityExplanation().then(d=> { if(seq===seqRef.current) setData(d); }).catch(e=> { if(seq===seqRef.current) setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [enabled]);
  return { data, loading, error };
}
