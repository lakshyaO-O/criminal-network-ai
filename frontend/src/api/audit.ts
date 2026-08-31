import { apiClient } from "./client";
import { DATA_SOURCE } from "../config";
import type { AuditTrailResponse } from "../types";

// M9A Audit — real backend only. Uses GET /api/audit/events per docs/api.md and backend-python/app/api.py.
// No fallback derivation from findings/evidence, no fabricated events.

function toQuery(params: Record<string, string | number | undefined | null>): string {
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");
  return qs ? `?${qs}` : "";
}

export async function getAuditTrail(params: {
  case_id?: string | null;
  analysis_type?: string | null;
  event_type?: string | null;
  entity_id?: string | null;
  root_entity_id?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  limit?: number;
  offset?: number;
}): Promise<AuditTrailResponse> {
  if (DATA_SOURCE === "mock") throw new Error("Audit unavailable in mock mode");
  // backend validates limit 1..100, offset >=0
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;
  if (limit < 1 || limit > 100) throw new Error("limit must be 1..100");
  if (offset < 0) throw new Error("offset must be >=0");
  const qs = toQuery({
    case_id: params.case_id ?? undefined,
    analysis_type: params.analysis_type ?? undefined,
    event_type: params.event_type ?? undefined,
    entity_id: params.entity_id ?? undefined,
    root_entity_id: params.root_entity_id ?? undefined,
    start_time: params.start_time ?? undefined,
    end_time: params.end_time ?? undefined,
    limit,
    offset,
  });
  return apiClient.get<AuditTrailResponse>(`/audit/events${qs}`);
}

export async function clearAuditEvents(): Promise<{ status: string; count: number }> {
  if (DATA_SOURCE === "mock") throw new Error("Audit unavailable in mock mode");
  return apiClient.post<{ status: string; count: number }>("/audit/events/clear", {});
}

// Legacy alias for hooks that previously used derived audit
export { getAuditTrail as getAuditEvents };
