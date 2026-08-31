import React from "react";
import { NetworkGraph } from "../graph/NetworkGraph";
import { FindingsPanel } from "./FindingsPanel";
import { EvidencePanel } from "./EvidencePanel";
import { PathExplorer } from "./PathExplorer";
import { LoadingState } from "../ui/LoadingState";
import { EmptyState } from "../ui/EmptyState";
import { ErrorState } from "../ui/ErrorState";
import type { Entity, Relationship, InvestigationSubgraphResponse, InvestigationFindingOut, InvestigationEvidenceOut, InvestigationPathResponse } from "../../types";

interface Props {
  caseId: string;
  rootId: string;
  depth: number;
  subgraph: InvestigationSubgraphResponse | null;
  entities: Entity[];
  relationships: Relationship[];
  findings: InvestigationFindingOut[];
  evidence: InvestigationEvidenceOut[];
  loading: boolean;
  error: string | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDepthChange: (d: number) => void;
  onClose: () => void;
  path: InvestigationPathResponse | null;
  pathLoading: boolean;
  pathError: string | null;
  onExplainFinding?: (findingId: string) => void;
  onExplainPath?: () => void;
}

export function InvestigationWorkspace({ caseId, rootId, depth, subgraph, entities, relationships, findings, evidence, loading, error, selectedId, onSelect, onDepthChange, onClose, path, pathLoading, pathError, onExplainFinding, onExplainPath }: Props) {
  if (loading) return <div className="border border-[#1e1e22] rounded-[8px] bg-[#111113] p-4"><LoadingState label="Loading investigation" /></div>;
  if (error) return <ErrorState title="Investigation unavailable" message={error} />;
  if (!subgraph) return <EmptyState title="No investigation" hint="Start an investigation from an entity to open a focused subgraph." />;

  const isEmpty = entities.length===0 && !loading && !error;

  return (
    <div className="flex flex-col gap-4">
      <div className="border border-[#1e1e22] rounded-[8px] bg-[#0f0f11] overflow-hidden">
        <div className="px-4 py-3 flex items-start justify-between gap-3 flex-wrap border-b border-[#1e1e22]">
          <div>
            <h2 className="text-[15px] font-semibold text-[#e8e8ea] tracking-tight">Investigation</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[11px] tracking-[0.06em] font-medium text-[#6b6b70]">CASE</span><span className="mono text-[11px] font-medium text-[#d4d4d8]">{caseId}</span>
              <span className="w-px h-3 bg-[#1e1e22]" aria-hidden />
              <span className="text-[11px] tracking-[0.06em] font-medium text-[#6b6b70]">ROOT</span><span className="mono text-[11px] font-medium text-[#e8e8ea]">{rootId}</span>
              <span className="w-px h-3 bg-[#1e1e22]" aria-hidden />
              <span className="mono text-[11px] text-[#8a8a90]">{entities.length} entities • {relationships.length} rels {subgraph.truncated ? "• truncated" : ""}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 bg-[#0a0a0c] rounded-[8px] border border-[#1e1e22] p-1">
              <span className="text-[10px] tracking-[0.08em] font-medium text-[#6b6b70] px-1">DEPTH</span>
              {[0,1,2,3,4,5,6].map(d=> (
                <button key={d} aria-pressed={depth===d} onClick={()=> onDepthChange(d)} aria-label={`Set depth ${d}`} className={`w-7 h-7 rounded-[6px] text-[12px] font-medium transition-colors ${depth===d?"bg-[#e8e8ea] text-[#0a0a0c]":"text-[#8a8a90] hover:bg-[#1a1a1e] hover:text-[#d4d4d8]"} focus:outline-none focus:ring-1 focus:ring-[#2a2a2e]`}>{d}</button>
              ))}
            </div>
            <button onClick={onClose} aria-label="Return to case network" className="text-[13px] px-3 py-1.5 rounded-[6px] bg-[#0a0a0c] border border-[#1e1e22] text-[#a1a1aa] hover:border-[#262629] hover:text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#2a2a2e]">← Network</button>
          </div>
        </div>
        {isEmpty ? <div className="p-4"><EmptyState title="Subgraph empty" hint="No entities within this investigation scope. Try increasing depth." /></div> : (
          <div className="relative bg-[#08080a]">
            <div className="min-h-[440px]">
              <NetworkGraph entities={entities} relationships={relationships} selectedId={selectedId} onSelect={onSelect} />
            </div>
            <div className="absolute top-3 left-3 flex items-center gap-2">
              <span className="mono text-[10px] tracking-[0.08em] font-medium text-amber-200/80 bg-amber-950/30 border border-amber-900/30 px-2 py-1 rounded-full">INVESTIGATION SUBGRAPH</span>
              <span className="mono text-[10px] text-[#8a8a90] bg-[#0a0a0c]/80 border border-[#1e1e22] px-2 py-1 rounded-full backdrop-blur">depth {depth} • root {rootId}</span>
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <FindingsPanel findings={findings} loading={loading} error={error} onSelectEntity={onSelect} onExplain={onExplainFinding} />
        <EvidencePanel evidence={evidence} loading={loading} error={error} onSelectEntity={onSelect} />
      </div>

      <div className="relative">
        <PathExplorer path={path} loading={pathLoading} error={pathError} onSelectEntity={onSelect} />
        {onExplainPath && path?.found && <button onClick={onExplainPath} aria-label="Explain path" className="absolute top-2 right-2 mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#1e1e22] border border-[#262629] text-[#8a8a90] hover:border-[#2e2e32]">Explain path</button>}
      </div>
      {subgraph.provenance?.length>0 && <div className="mono text-[10px] text-[#6b6b70] border border-[#262629] rounded-[8px] bg-[#17171a] px-3 py-1.5">provenance: {subgraph.provenance.length} entries • statistics: {JSON.stringify(subgraph.statistics).slice(0,120)}</div>}
    </div>
  );
}
