import React from "react";
import type { InvestigationEvidenceOut } from "../../types";
import { LoadingState } from "../ui/LoadingState";
import { EmptyState } from "../ui/EmptyState";
import { ErrorState } from "../ui/ErrorState";

export function EvidencePanel({ evidence, loading, error, onSelectEntity, onSelectRelationship }: { evidence: InvestigationEvidenceOut[]; loading: boolean; error: string | null; onSelectEntity: (id: string) => void; onSelectRelationship?: (id: string) => void }) {
  if (loading) return <div className="border border-[#262629] rounded-[8px] bg-[#17171a] p-2"><LoadingState label="Loading evidence" /></div>;
  if (error) return <ErrorState title="Evidence unavailable" message={error} />;
  if (!evidence.length) return <EmptyState title="No evidence" hint="No evidence items for this investigation (M8A)." />;

  return (
    <div className="border border-[#262629] rounded-[8px] bg-[#17171a] overflow-hidden" role="region" aria-label="Evidence">
      <div className="px-3 py-2 border-b border-[#262629] flex justify-between">
        <span className="mono text-[11px] font-semibold text-[#d4d4d8]">EVIDENCE</span>
        <span className="mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">{evidence.length}</span>
      </div>
      <div className="divide-y divide-[#1e1e22] max-h-[420px] overflow-auto">
        {evidence.map(ev=> (
          <div key={ev.evidence_id} className="px-3 py-2.5">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">{ev.evidence_type}</span>
              {ev.created_at && <span className="mono text-[10px] text-[#6b6b70]">{new Date(ev.created_at).toLocaleString()}</span>}
            </div>
            <div className="mono text-[11px] text-[#8a8a90] leading-snug mt-1">{ev.description}</div>
            <div className="flex gap-1 mt-1.5 flex-wrap">
              {ev.entity_ids.slice(0,4).map(e=> <button key={e} onClick={()=> onSelectEntity(e)} className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] hover:border-[#2e2e32]">{e}</button>)}
              {ev.relationship_ids.slice(0,4).map(r=> <button key={r} onClick={()=> onSelectRelationship?.(r)} className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22] text-[#6b6b70] hover:border-[#262629]">{r}</button>)}
            </div>
            {ev.provenance?.length>0 && <div className="mono text-[10px] text-[#6b6b70] mt-1 truncate">provenance: {ev.provenance.length} • {ev.indicator_ids.length ? `${ev.indicator_ids.length} indicators` : ""}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}
