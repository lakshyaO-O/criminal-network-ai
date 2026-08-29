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
  if (loading) return <div className="border border-[#262629] rounded-[8px] bg-[#17171a] p-4"><LoadingState label="Loading investigation" /></div>;
  if (error) return <ErrorState title="Investigation unavailable" message={error} />;
  if (!subgraph) return <EmptyState title="No investigation" hint="Start an investigation from an entity." />;

  const isEmpty = entities.length===0 && !loading && !error;

  return (
    <div className="flex flex-col gap-3">
      <div className="border border-[#262629] rounded-[8px] bg-[#17171a] px-3 py-2 flex items-center justify-between gap-2 flex-wrap">
        <div className="mono">
          <div className="text-[11px] font-semibold text-[#d4d4d8]">INVESTIGATION — <span className="text-[#e8e8ea]">{rootId}</span> <span className="text-[#6b6b70]">depth {depth}</span></div>
          <div className="text-[10px] text-[#6b6b70]">CASE: {caseId} • {entities.length} entities • {relationships.length} relationships • root highlighted {subgraph.truncated ? "• truncated" : ""}</div>
        </div>
        <div className="flex items-center gap-1">
          <div className="flex items-center gap-1 mr-2">
            <span className="mono text-[10px] text-[#6b6b70]">DEPTH</span>
            {[1,2,3,4,5,6].map(d=> (
              <button key={d} aria-pressed={depth===d} onClick={()=> onDepthChange(d)} className={`w-6 h-6 rounded-[6px] border mono text-[11px] ${depth===d?"bg-[#1e1e22] border-[#2e2e32] text-white":"border-[#262629] text-[#8a8a90] hover:bg-[#1e1e22]"}`}>{d}</button>
            ))}
          </div>
          <button onClick={onClose} aria-label="Return to case network" className="mono text-[11px] px-2 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#d4d4d8] hover:bg-[#1e1e22] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">← return to CASE NETWORK</button>
        </div>
      </div>

      {isEmpty ? <EmptyState title="Subgraph empty" hint="No entities within this investigation scope." /> : (
        <div className="min-h-[420px] border border-[#262629] rounded-[8px] overflow-hidden relative">
          <NetworkGraph entities={entities} relationships={relationships} selectedId={selectedId} onSelect={onSelect} />
          <div className="absolute top-2 left-2 mono text-[10px] px-2 py-1 rounded-[6px] bg-amber-950/30 border border-amber-900/30 text-amber-200/80">INVESTIGATION SUBGRAPH • M8A</div>
          <div className="absolute bottom-2 left-2 mono text-[10px] text-[#6b6b70]">root {rootId} • depth {depth} {subgraph.truncated ? "• truncated" : ""}</div>
        </div>
      )}

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
