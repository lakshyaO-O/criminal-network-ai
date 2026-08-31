import { useEffect, useState, useRef } from "react";
import { DATA_SOURCE } from "../config";
import type { AuditTrailResponse } from "../types";
import { getAuditTrail } from "../api/audit";
import { ApiError } from "../api/client";

export function useAuditTrail(params: {
  case_id?: string | null;
  analysis_type?: string | null;
  event_type?: string | null;
  entity_id?: string | null;
  root_entity_id?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  limit?: number;
  offset?: number;
}) {
  const [data, setData] = useState<AuditTrailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seqRef = useRef(0);
  const key = JSON.stringify(params);
  useEffect(() => {
    if (DATA_SOURCE==="mock") { setData({ events: [], count: 0, total: 0, limit: params.limit ?? 50, offset: 0 }); setError("Audit unavailable in mock mode"); setLoading(false); return; }
    const seq = ++seqRef.current;
    setLoading(true); setError(null); setData(null);
    getAuditTrail(params).then(d=> { if(seq===seqRef.current) setData(d); }).catch(e=> { if(seq===seqRef.current) setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e)); }).finally(()=> { if(seq===seqRef.current) setLoading(false); });
  }, [key]);
  return { data, loading, error };
}
