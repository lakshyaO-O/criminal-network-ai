import { useEffect, useState, useRef, useCallback } from "react";
import { DATA_SOURCE } from "../config";
import type {
  AIStatusResponse,
  AIExtractEntitiesResponse,
  AIExtractRelationshipsResponse,
  AIAnalyzeResponse,
  AIEntityMention,
} from "../types";
import { getAIStatus, extractEntities, extractRelationships, analyzeWithAI } from "../api/ai";
import { ApiError } from "../api/client";

// Follows M10B reliability: AbortController + seq guard + stale protection

export function useAIStatus(pollMs: number | null = null) {
  const [data, setData] = useState<AIStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);

  const refresh = useCallback(async () => {
    if (DATA_SOURCE === "mock") {
      setData(null);
      setError("AI unavailable in mock mode");
      setLoading(false);
      return;
    }
    const seq = ++seqRef.current;
    setLoading(true);
    setError(null);
    try {
      const r = await getAIStatus();
      if (seq !== seqRef.current) return;
      setData(r);
    } catch (e: unknown) {
      if (seq !== seqRef.current) return;
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));
    } finally {
      if (seq === seqRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    if (pollMs && DATA_SOURCE !== "mock") {
      const id = setInterval(refresh, pollMs);
      return () => clearInterval(id);
    }
  }, [refresh, pollMs]);

  return { data, loading, error, refresh };
}

export function useAIAnalysis() {
  const [data, setData] = useState<AIAnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);

  const analyze = useCallback(
    async (params: {
      analysis_type: string;
      case_id?: string | null;
      root_entity_id?: string | null;
      text?: string | null;
      graph_snapshot?: Record<string, unknown> | null;
      provider?: string | null;
    }) => {
      if (DATA_SOURCE === "mock") {
        setError("AI unavailable in mock mode");
        return;
      }
      const seq = ++seqRef.current;
      setLoading(true);
      setError(null);
      setData(null);
      try {
        const r = await analyzeWithAI(params);
        if (seq !== seqRef.current) return;
        setData(r);
      } catch (e: unknown) {
        if (seq !== seqRef.current) return;
        setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));
      } finally {
        if (seq === seqRef.current) setLoading(false);
      }
    },
    []
  );

  const reset = useCallback(() => {
    seqRef.current++;
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, loading, error, analyze, reset };
}

export function useAIEntityExtraction() {
  const [data, setData] = useState<AIExtractEntitiesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);

  const extract = useCallback(async (params: { text: string; source_id?: string | null; provider?: string | null }) => {
    if (DATA_SOURCE === "mock") {
      setError("AI unavailable in mock mode");
      return;
    }
    const seq = ++seqRef.current;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const r = await extractEntities(params);
      if (seq !== seqRef.current) return;
      setData(r);
    } catch (e: unknown) {
      if (seq !== seqRef.current) return;
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));
    } finally {
      if (seq === seqRef.current) setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    seqRef.current++;
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, loading, error, extract, reset };
}

export function useAIRelationshipExtraction() {
  const [data, setData] = useState<AIExtractRelationshipsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);

  const extract = useCallback(
    async (params: {
      text: string;
      source_id?: string | null;
      entities: AIEntityMention[];
      structured_records?: Record<string, unknown>[];
      provider?: string | null;
    }) => {
      if (DATA_SOURCE === "mock") {
        setError("AI unavailable in mock mode");
        return;
      }
      const seq = ++seqRef.current;
      setLoading(true);
      setError(null);
      setData(null);
      try {
        const r = await extractRelationships(params);
        if (seq !== seqRef.current) return;
        setData(r);
      } catch (e: unknown) {
        if (seq !== seqRef.current) return;
        setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));
      } finally {
        if (seq === seqRef.current) setLoading(false);
      }
    },
    []
  );

  const reset = useCallback(() => {
    seqRef.current++;
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, loading, error, extract, reset };
}
