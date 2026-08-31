import { useEffect, useState, useRef, useCallback } from "react";
import { DATA_SOURCE } from "../config";
import { getHealth } from "../api/entities";
import type { HealthResponse } from "../types";

export type ConnectionState = "connecting" | "connected" | "offline";

export function useHealth(pollMs = 30000) {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(DATA_SOURCE === "api");
  const [connectionState, setConnectionState] = useState<ConnectionState>(DATA_SOURCE === "mock" ? "connected" : "connecting");
  const seqRef = useRef(0);
  const retryCountRef = useRef(0);

  const fetchHealth = useCallback(async (isInitial = false) => {
    if (DATA_SOURCE === "mock") {
      setData({ status: "ok", service: "criminal-network-analysis", version: "mock-1.0.0" });
      setError(null);
      setLoading(false);
      setConnectionState("connected");
      return;
    }
    const seq = ++seqRef.current;
    if (isInitial) setLoading(true);
    try {
      const h = await getHealth();
      if (seq !== seqRef.current) return;
      setData(h);
      setError(null);
      setConnectionState("connected");
      retryCountRef.current = 0;
    } catch (e: unknown) {
      if (seq !== seqRef.current) return;
      const msg = e instanceof Error ? e.message : String(e);
      // Only mark offline after 2 consecutive failures to avoid flapping on single timeout
      retryCountRef.current += 1;
      if (retryCountRef.current >= 2) {
        setError(msg);
        setConnectionState("offline");
      } else {
        // Keep as connecting on first failure, will retry shortly
        setConnectionState("connecting");
      }
    } finally {
      if (seq === seqRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth(true);
    const id = setInterval(() => fetchHealth(false), pollMs);
    return () => { seqRef.current++; clearInterval(id); };
  }, [fetchHealth, pollMs]);

  const retry = useCallback(() => {
    retryCountRef.current = 0;
    setConnectionState("connecting");
    fetchHealth(true);
  }, [fetchHealth]);

  return { data, error, loading, isMock: DATA_SOURCE === "mock", connectionState, retry };
}
