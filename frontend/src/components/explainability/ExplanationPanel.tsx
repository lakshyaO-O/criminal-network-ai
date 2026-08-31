import React from "react";
import { motion } from "framer-motion";
import type { ExplanationResponse } from "../../types";
import { LoadingState } from "../ui/LoadingState";
import { ErrorState } from "../ui/ErrorState";
import { EmptyState } from "../ui/EmptyState";
import { ProvenancePanel } from "./ProvenancePanel";

export function ExplanationPanel({ explanation, loading, error, onClose }: { explanation: ExplanationResponse | null; loading: boolean; error: string | null; onClose?: () => void }) {
  if (loading) return <div className="border border-[#262629] rounded-[8px] bg-[#17171a] p-3"><LoadingState label="Loading explanation" /></div>;
  if (error) return <ErrorState title="Explanation unavailable" message={error} />;
  if (!explanation) return <EmptyState title="No explanation selected" hint="Select a finding, indicator, or entity to explain." />;

  const limitationsList = typeof explanation.limitations === "string" ? [explanation.limitations] : Array.isArray(explanation.limitations) ? explanation.limitations as string[] : [];
  const displayTitle = explanation.title || explanation.summary.slice(0, 80);
  const displayTarget = explanation.target_id || explanation.explanation_id;
  const obsData = explanation.observed_data;
  const analytic = explanation.analytical_interpretation;

  return (
    <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }} className="border border-[#262629] rounded-[8px] bg-[#17171a] overflow-hidden flex flex-col" role="region" aria-label={`Explanation ${displayTitle}`}>
      <div className="px-3 py-2 border-b border-[#262629] bg-[#0e0e10]/50 flex justify-between items-start gap-2">
        <div>
          <div className="mono text-[10px] tracking-wide text-[#8a8a90]">{explanation.analysis_type.toUpperCase()} • {explanation.explanation_id}</div>
          <div className="text-[12px] font-medium text-[#d4d4d8] mono">{displayTitle}</div>
          <div className="mono text-[10px] text-[#6b6b70] mt-0.5">{explanation.generated_at && !isNaN(new Date(explanation.generated_at).getTime()) ? new Date(explanation.generated_at).toLocaleString() : ""} • {displayTarget}</div>
        </div>
        {onClose && <button onClick={onClose} aria-label="Close explanation" className="mono text-[10px] px-2 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] hover:text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">× close</button>}
      </div>

      <div className="px-3 py-2 border-b border-[#262629] bg-[#1e1e22]/30">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">SUMMARY</div>
        <div className="mono text-[11px] text-[#d4d4d8] leading-snug">{explanation.summary}</div>
      </div>

      <div className="px-3 py-2 border-b border-[#262629]">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">OBSERVED DATA</div>
        <ul className="list-disc list-inside mono text-[11px] text-[#a1a1aa] space-y-0.5">
          {explanation.observations.map((o,i)=> <li key={i}>{o}</li>)}
        </ul>
        {obsData?.entity && <div className="mono text-[10px] text-[#6b6b70] mt-2">observed entity: {JSON.stringify(obsData.entity).slice(0,140)}</div>}
        {obsData?.relationships && obsData.relationships.length>0 && <div className="mono text-[10px] text-[#6b6b70]">observed relationships: {obsData.relationships.length} (showing {Math.min(3, obsData.relationships.length)})</div>}
      </div>

      <div className="px-3 py-2 border-b border-[#262629]">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">ANALYTICAL INTERPRETATION</div>
        <div className="mono text-[11px] text-[#a1a1aa] leading-snug">{explanation.methodology}</div>
        {Object.keys(explanation.parameters).length>0 && (
          <div className="mt-2 mono text-[10px] text-[#6b6b70]">parameters: {JSON.stringify(explanation.parameters).slice(0,220)}</div>
        )}
        {explanation.thresholds && Object.keys(explanation.thresholds).length>0 && (
          <div className="mono text-[10px] text-[#6b6b70] mt-1">thresholds: {JSON.stringify(explanation.thresholds).slice(0,220)}</div>
        )}
        {analytic && <div className="mono text-[10px] text-[#6b6b70] mt-2">analytical: {JSON.stringify(analytic).slice(0,180)}</div>}
      </div>

      <div className="px-3 py-2 border-b border-[#262629]">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">SUPPORTING EVIDENCE</div>
        {explanation.contributing_entities.length===0 && explanation.contributing_relationships.length===0 && explanation.supporting_evidence.length===0 ? (
          <span className="mono text-[11px] text-[#6b6b70]">No supporting evidence listed</span>
        ) : (
          <>
            {explanation.contributing_entities.length>0 && <div className="flex flex-wrap gap-1 mt-1">{explanation.contributing_entities.slice(0,6).map(e=> <span key={e} className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">{e}</span>)}</div>}
            {explanation.contributing_relationships.length>0 && <div className="flex flex-wrap gap-1 mt-1">{explanation.contributing_relationships.slice(0,6).map(r=> <span key={r} className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22] text-[#6b6b70]">{r}</span>)}</div>}
            {explanation.supporting_evidence.length>0 && <div className="mono text-[10px] text-[#6b6b70] mt-1">{explanation.supporting_evidence.length} evidence refs: {explanation.supporting_evidence.slice(0,4).join(", ")}</div>}
          </>
        )}
      </div>

      <div className="px-3 py-2 border-b border-[#262629]">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">PROVENANCE</div>
        <ProvenancePanel provenance={explanation.provenance} />
      </div>

      {(explanation.lineage && Object.keys(explanation.lineage).length>0) && (
        <div className="px-3 py-2 border-b border-[#262629] bg-[#0e0e10]/20">
          <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">LINEAGE</div>
          <div className="mono text-[10px] text-[#6b6b70] break-all">dataset {String((explanation.lineage as Record<string,string>).dataset_id || "")} • deterministic {String((explanation.lineage as Record<string,unknown>).deterministic)} • {(explanation.lineage as Record<string,string>).algorithm || ""}</div>
          <div className="mono text-[10px] text-[#6b6b70]">inputs: {JSON.stringify((explanation.lineage as Record<string,unknown>).inputs || {}).slice(0,120)}</div>
        </div>
      )}

      {(explanation.reproducibility && Object.keys(explanation.reproducibility).length>0) && (
        <div className="px-3 py-2 border-b border-[#262629]">
          <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">REPRODUCIBILITY</div>
          <div className="mono text-[10px] text-[#6b6b70]">result {String((explanation.reproducibility as Record<string,string>).result_id || explanation.explanation_id)} • deterministic {String((explanation.reproducibility as Record<string,unknown>).deterministic)}</div>
        </div>
      )}

      <div className="px-3 py-2 bg-[#0e0e10]/30">
        <div className="mono text-[10px] tracking-wide text-[#8a8a90] mb-1">LIMITATIONS</div>
        <ul className="list-disc list-inside mono text-[11px] text-[#6b6b70] space-y-0.5">
          {limitationsList.filter(Boolean).map((l,i)=> <li key={i}>{l}</li>)}
        </ul>
      </div>
    </motion.div>
  );
}
