import React from "react";
import { LoadingState } from "../ui/LoadingState";
import { EmptyState } from "../ui/EmptyState";
import { ErrorState } from "../ui/ErrorState";
import type { InvestigationPathResponse } from "../../types";

// M8A-native: nodes/edges + relationship_sequence, hop_count
export function PathExplorer({ path, loading, error, onSelectEntity }: { path: InvestigationPathResponse | null; loading: boolean; error: string | null; onSelectEntity: (id: string) => void }) {
  if (loading) return <div className="border border-[#262629] rounded-[8px] bg-[#17171a] p-2"><LoadingState label="Finding path" /></div>;
  if (error) return <ErrorState title="Path unavailable" message={error} />;
  if (!path) return <EmptyState title="No path selected" hint="Enter source → target and find a multi-hop path via M8A." />;
  if (!path.found) return <EmptyState title="No path found" hint="No connection within max depth between selected entities." />;

  const nodes = path.nodes as { entity_id: string; entity_type?: string; properties?: Record<string, unknown> }[];
  const edges = path.edges as { relationship_id: string; relationship_type: string; source_id: string; target_id: string }[];
  const hopCount = path.hop_count ?? nodes.length - 1;

  return (
    <div className="border border-[#262629] rounded-[8px] bg-[#17171a] overflow-hidden" role="region" aria-label="Path explorer">
      <div className="px-3 py-2 border-b border-[#262629] flex justify-between items-center gap-2">
        <span className="mono text-[11px] font-semibold text-[#d4d4d8]">PATH — {hopCount} hop{hopCount!==1?"s":""}</span>
        <span className="mono text-[10px] text-[#6b6b70] truncate">{nodes[0]?.entity_id} → {nodes[nodes.length-1]?.entity_id}</span>
      </div>
      <div className="px-3 py-3 flex flex-col items-start gap-0">
        {nodes.map((n, i) => {
          const eid = String(n.entity_id);
          const rel = edges[i];
          return (
            <div key={eid + i} className="flex items-start gap-2 w-full">
              <div className="flex flex-col items-center">
                <button onClick={()=> onSelectEntity(eid)} aria-label={`Inspect ${eid}`} className="w-7 h-7 rounded-full bg-[#0e0e10] border border-[#262629] hover:border-[#2e2e32] mono text-[10px] text-[#d4d4d8] flex items-center justify-center focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">{i+1}</button>
                {i < nodes.length -1 && <div className="w-px h-6 bg-[#262629] my-1" aria-hidden />}
              </div>
              <div className="flex-1 min-w-0 pb-2">
                <button onClick={()=> onSelectEntity(eid)} className="mono text-[11px] text-[#d4d4d8] hover:text-white text-left truncate focus:outline-none focus:underline">{eid} {n.entity_type ? <span className="text-[#6b6b70]">({String(n.entity_type)})</span> : null}</button>
                <div className="mono text-[10px] text-[#6b6b70]">hop {i} • {String(n.entity_type || "entity")}</div>
                {rel && (
                  <div className="mt-1 mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] inline-block" title={String(rel.relationship_id)}>
                    {String(rel.relationship_type)} <span className="text-[#6b6b70]">• {String(rel.source_id)}→{String(rel.target_id)}</span>
                  </div>
                )}
                {/* fallback to relationship_sequence if edges missing */}
                {!rel && path.relationship_sequence?.[i] && (
                  <div className="mt-1 mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] inline-block">{String(path.relationship_sequence[i])}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {path.provenance?.length>0 && <div className="px-3 py-1.5 mono text-[10px] text-[#6b6b70] border-t border-[#262629] bg-[#0e0e10]/30">provenance: {path.provenance.length} entries</div>}
    </div>
  );
}
