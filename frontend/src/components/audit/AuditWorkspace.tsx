import React, { useState } from "react";
import { LoadingState } from "../ui/LoadingState";
import { EmptyState } from "../ui/EmptyState";
import { ErrorState } from "../ui/ErrorState";
import type { AuditTrailResponse } from "../../types";
import { ProvenancePanel } from "../explainability/ProvenancePanel";

export function AuditWorkspace({ audit, loading, error, caseId, onCaseChange }: {
  audit: AuditTrailResponse | null;
  loading: boolean;
  error: string | null;
  caseId: string | null;
  onCaseChange: (c: string | null) => void;
}) {
  const [analysisFilter, setAnalysisFilter] = useState<string>("all");
  const [eventFilter, setEventFilter] = useState<string>("all");

  if (loading) return <div className="border border-[#262629] rounded-[8px] bg-[#17171a] p-3"><LoadingState label="Loading audit trail" /></div>;
  if (error) return <ErrorState title="Audit unavailable" message={error} />;
  if (!audit || audit.events.length===0) return <EmptyState title="No audit events" hint={caseId ? `No audit trail for ${caseId}. Run an investigation or explainability query to generate events.` : "Select a case to view audit trail."} />;

  const analysisTypes = Array.from(new Set(audit.events.map(e=> e.analysis_type).filter(Boolean) as string[])).sort();
  const eventTypes = Array.from(new Set(audit.events.map(e=> e.event_type))).sort();

  let filtered = audit.events;
  if (analysisFilter!=="all") filtered = filtered.filter(e=> e.analysis_type===analysisFilter);
  if (eventFilter!=="all") filtered = filtered.filter(e=> e.event_type===eventFilter);

  const isTruncated = audit.count > filtered.length || audit.total > audit.count;

  return (
    <div className="border border-[#262629] rounded-[8px] bg-[#17171a] overflow-hidden flex flex-col" role="region" aria-label="Audit trail">
      <div className="px-3 py-2 border-b border-[#262629] bg-[#0e0e10]/50 flex flex-wrap gap-2 items-center justify-between">
        <div className="mono text-[11px] font-semibold text-[#d4d4d8]">AUDIT TRAIL {caseId ? `— ${caseId}` : ""} <span className="text-[#6b6b70] font-normal">• {audit.count}/{audit.total} events {isTruncated ? "• truncated" : ""} limit {audit.limit} offset {audit.offset}</span></div>
        <div className="flex gap-1 items-center">
          <select value={caseId ?? ""} onChange={e=> { const v = e.target.value; if (v !== caseId) onCaseChange(v || null); }} aria-label="Filter by case" className="mono text-[10px] px-1.5 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">
            <option value="">all cases</option>
            <option value="case-00001">case-00001</option>
            <option value="case-00002">case-00002</option>
            <option value="case-00003">case-00003</option>
            <option value="case-00004">case-00004</option>
          </select>
          <select value={analysisFilter} onChange={e=> setAnalysisFilter(e.target.value)} aria-label="Filter by analysis" className="mono text-[10px] px-1.5 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">
            <option value="all">all analysis</option>
            {analysisTypes.map(a=> <option key={a} value={a}>{a}</option>)}
          </select>
          <select value={eventFilter} onChange={e=> setEventFilter(e.target.value)} aria-label="Filter by event type" className="mono text-[10px] px-1.5 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">
            <option value="all">all events</option>
            {eventTypes.map(ev=> <option key={ev} value={ev}>{ev}</option>)}
          </select>
        </div>
      </div>

      <div className="divide-y divide-[#1e1e22] max-h-[600px] overflow-auto">
        {filtered.map(ev=> (
          <div key={ev.audit_id} className="px-3 py-2.5 flex gap-3">
            <div className="mono text-[10px] text-[#6b6b70] shrink-0 w-[72px]">{ev.timestamp && !isNaN(new Date(ev.timestamp).getTime()) ? new Date(ev.timestamp).toLocaleTimeString() : ev.timestamp}<br/><span className="text-[9px]">{ev.timestamp && !isNaN(new Date(ev.timestamp).getTime()) ? new Date(ev.timestamp).toLocaleDateString() : ""}</span></div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">{ev.event_type}</span>
                {ev.analysis_type && <span className="mono text-[10px] text-[#6b6b70]">{ev.analysis_type}</span>}
                {(ev.object_id || ev.entity_id) && <span className="mono text-[10px] text-[#8a8a90]">• {ev.object_id || ev.entity_id}</span>}
                <span className={`mono text-[10px] px-1 py-0 rounded border ${ev.status==="completed" ? "border-emerald-500/20 text-emerald-200/70" : "border-[#262629] text-[#8a8a90]"}`}>{ev.status}</span>
              </div>
              <div className="mono text-[11px] text-[#d4d4d8] mt-1 leading-snug">{ev.object_id || ev.entity_id || ev.audit_id} — {ev.analysis_type || ev.event_type}</div>
              {ev.case_id && <div className="mono text-[10px] text-[#6b6b70]">case {ev.case_id} {ev.root_entity_id ? `• root ${ev.root_entity_id}` : ""}</div>}
              {Object.keys(ev.parameters||{}).length>0 && <div className="mono text-[10px] text-[#6b6b70] mt-0.5">params: {JSON.stringify(ev.parameters).slice(0,160)}</div>}
              {ev.provenance?.length>0 && <div className="mt-1"><ProvenancePanel provenance={ev.provenance as never} /></div>}
            </div>
          </div>
        ))}
        {filtered.length===0 && <div className="p-4"><EmptyState title="No events for filter" hint="Adjust analysis/event type filters. Backend supports limit 1..100, offset >=0." /></div>}
      </div>
      <div className="px-3 py-1.5 mono text-[10px] text-[#6b6b70] border-t border-[#262629] bg-[#0e0e10]/30">Deterministic ordering by timestamp,audit_id • bounded list 1..100 • {filtered.length}/{audit.count} shown • total {audit.total} • no secrets logged</div>
    </div>
  );
}
