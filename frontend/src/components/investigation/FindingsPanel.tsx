import React from "react";
import type { InvestigationFindingOut } from "../../types";
import { LoadingState } from "../ui/LoadingState";
import { EmptyState } from "../ui/EmptyState";
import { ErrorState } from "../ui/ErrorState";

export function FindingsPanel({ findings, loading, error, onSelectEntity, onExplain }: { findings: InvestigationFindingOut[]; loading: boolean; error: string | null; onSelectEntity: (id: string) => void; onExplain?: (findingId: string) => void }) {
  if (loading) return <div className="border border-[#262629] rounded-[8px] bg-[#17171a] p-2"><LoadingState label="Loading findings" /></div>;
  if (error) return <ErrorState title="Findings unavailable" message={error} />;
  if (!findings.length) return <EmptyState title="No findings" hint="No candidate findings for this investigation scope (M8A)." />;

  return (
    <div className="border border-[#262629] rounded-[8px] bg-[#17171a] overflow-hidden" role="region" aria-label="Findings">
      <div className="px-3 py-2 border-b border-[#262629] flex justify-between">
        <span className="mono text-[11px] font-semibold text-[#d4d4d8]">FINDINGS</span>
        <span className="mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">{findings.length}</span>
      </div>
      <div className="divide-y divide-[#1e1e22] max-h-[420px] overflow-auto">
        {findings.map(f=> (
          <div key={f.finding_id} className="px-3 py-2.5">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="mono text-[10px] tracking-wide text-[#8a8a90]">{f.finding_type}</span>
              <span className={`mono text-[9px] px-1 rounded border ${f.severity==="HIGH"?"border-amber-500/20 text-amber-200/80 bg-amber-500/10":f.severity==="MEDIUM"?"border-[#2e2e32] text-[#d4d4d8] bg-[#1e1e22]":"border-[#262629] text-[#8a8a90]"}`}>{f.severity}</span>
              {f.created_at && <span className="mono text-[10px] text-[#6b6b70]">{new Date(f.created_at).toLocaleString()}</span>}
            </div>
            <div className="mono text-[11px] font-medium text-[#d4d4d8] mt-1">{f.title}</div>
            <div className="mono text-[11px] text-[#8a8a90] leading-snug mt-1">{f.explanation}</div>
            {(f.centrality_context || f.community_context) && (
              <div className="mono text-[10px] text-[#6b6b70] mt-1.5">
                {f.centrality_context ? `centrality ${JSON.stringify(f.centrality_context).slice(0,80)}` : ""}
                {f.community_context ? ` • community ${JSON.stringify(f.community_context).slice(0,80)}` : ""}
              </div>
            )}
            {(f.entity_ids.length>0 || f.relationship_ids.length>0) && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                {f.entity_ids.slice(0,4).map(e=> <button key={e} onClick={()=> onSelectEntity(e)} className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] hover:border-[#2e2e32]">{e}</button>)}
                {f.relationship_ids.slice(0,3).map(r=> <span key={r} className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22] text-[#6b6b70]">{r}</span>)}
              </div>
            )}
            {f.supporting_paths.length>0 && <div className="mono text-[10px] text-[#6b6b70] mt-1">{f.supporting_paths.length} supporting path(s)</div>}
            {f.evidence.length>0 && <div className="mono text-[10px] text-[#6b6b70] mt-1">{f.evidence.length} evidence items</div>}
            {f.provenance?.length>0 && <div className="mono text-[10px] text-[#6b6b70] mt-1 truncate">provenance: {f.provenance.length} entries</div>}
            {onExplain && <button onClick={()=> onExplain(f.finding_id)} aria-label={`Explain finding ${f.finding_id}`} className="mt-2 mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#1e1e22] border border-[#262629] text-[#8a8a90] hover:border-[#2e2e32] hover:text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">Explain →</button>}
          </div>
        ))}
      </div>
    </div>
  );
}
