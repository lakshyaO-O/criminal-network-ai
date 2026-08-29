import { apiClient } from "./client";
import { DATA_SOURCE } from "../config";
import type { AuditEvent, AuditTrailResponse } from "../types";
import { getInvestigationFindings, getInvestigationEvidence } from "./investigations";

// M9A Audit adapter — when backend supports GET /api/audit/trail, use it; otherwise derive audit trail from M8A findings/evidence provenance.

async function tryM9Audit<T>(path: string, fallback: () => Promise<T>): Promise<T> {
  if (DATA_SOURCE === "mock") {
    // In mock, audit is explicitly unavailable, not fake
    throw new Error("Audit unavailable in mock mode");
  }
  try {
    return await apiClient.get<T>(path);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.includes("404") || msg.includes("Not Found")) {
      return fallback();
    }
    throw e;
  }
}

function toAuditEventsFromFindings(findings: { finding_id: string; finding_type: string; title: string; created_at: string; case_id?: string | null; root_entity_id?: string | null; provenance: unknown[] }[], evidence: { evidence_id: string; evidence_type: string; created_at: string; provenance: unknown[] }[], caseId?: string | null): AuditEvent[] {
  const events: AuditEvent[] = [];
  findings.forEach(f=> {
    events.push({
      audit_id: `audit-${f.finding_id}`,
      case_id: caseId ?? null,
      root_entity_id: (f as unknown as { root_entity_id?: string }).root_entity_id ?? null,
      event_type: "finding_generated",
      analysis_type: f.finding_type,
      target_id: f.finding_id,
      summary: `${f.finding_type}: ${f.title}`,
      timestamp: f.created_at,
      provenance: (f.provenance as AuditEvent["provenance"]) || []
    });
  });
  evidence.forEach(ev=> {
    events.push({
      audit_id: `audit-${ev.evidence_id}`,
      case_id: caseId ?? null,
      event_type: "evidence_generated",
      analysis_type: ev.evidence_type,
      target_id: ev.evidence_id,
      summary: `${ev.evidence_type}: ${ev.evidence_id}`,
      timestamp: ev.created_at,
      provenance: (ev.provenance as AuditEvent["provenance"]) || []
    });
  });
  return events.sort((a,b)=> new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
}

export async function getAuditTrail(params: {
  case_id?: string | null;
  root_entity_id?: string | null;
  analysis_type?: string | null;
  event_type?: string | null;
  limit?: number;
}): Promise<AuditTrailResponse> {
  return tryM9Audit<AuditTrailResponse>(`/audit/trail?case_id=${params.case_id ?? ""}&root_entity_id=${params.root_entity_id ?? ""}&analysis_type=${params.analysis_type ?? ""}&event_type=${params.event_type ?? ""}&limit=${params.limit ?? 50}`, async () => {
    // Fallback: derive from M8A findings/evidence (real backend truth, not invented)
    const [findsRes, evList] = await Promise.all([
      getInvestigationFindings({ case_id: params.case_id ?? undefined, root_entity_id: params.root_entity_id ?? undefined, depth: 2 }),
      getInvestigationEvidence({ case_id: params.case_id ?? undefined, root_entity_id: params.root_entity_id ?? undefined, depth: 2 })
    ]);
    const events = toAuditEventsFromFindings(
      findsRes.findings as unknown as { finding_id: string; finding_type: string; title: string; created_at: string; provenance: unknown[] }[],
      evList as unknown as { evidence_id: string; evidence_type: string; created_at: string; provenance: unknown[] }[],
      params.case_id ?? null
    );
    let filtered = events;
    if (params.analysis_type) filtered = filtered.filter(e=> e.analysis_type === params.analysis_type);
    if (params.event_type) filtered = filtered.filter(e=> e.event_type === params.event_type);
    filtered = filtered.slice(0, params.limit ?? 50);
    return { case_id: params.case_id ?? null, events: filtered, count: filtered.length, truncated: events.length > (params.limit ?? 50), generated_at: new Date().toISOString() };
  });
}
