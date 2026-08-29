import { useEffect, useState, useRef } from "react";
import { DATA_SOURCE } from "../config";
import { getHealth } from "../api/entities";
import type { HealthResponse } from "../types";

export function useHealth(pollMs = 30000) {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchHealth() {
      if (DATA_SOURCE === "mock") { setData({ status: "ok", service: "criminal-network-analysis", version: "mock-1.0.0" }); setError(null); setLoading(false); return; }
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setLoading(true);
      try {
        const h = await getHealth();
        if (!cancelled && !ctrl.signal.aborted) { setData(h); setError(null); }
      } catch (e: unknown) {
        if (!cancelled && !ctrl.signal.aborted) setError(e instanceof Error ? e.message : String(e));
      } finally { if (!cancelled && !ctrl.signal.aborted) setLoading(false); }
    }
    fetchHealth();
    const id = setInterval(fetchHealth, pollMs);
    return () => { cancelled = true; clearInterval(id); abortRef.current?.abort(); };
  }, [pollMs]);

  return { data, error, loading, isMock: DATA_SOURCE === "mock" };
}
