import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Entity, Relationship, TimelineEvent, Alert } from "../../types";
import { Badge } from "../ui/Badge";
import { EmptyState } from "../ui/EmptyState";
import { LoadingState } from "../ui/LoadingState";

export function EntityDetails({ entity, relationships, events, alerts, onSelectRelated, onStartInvestigation, onExplain, loading, error }: {
  entity: Entity | null; relationships: Relationship[]; events?: TimelineEvent[]; alerts?: Alert[]; onSelectRelated?: (id: string) => void; onStartInvestigation?: (id: string) => void; onExplain?: (id: string) => void; loading?: boolean; error?: string | null;
}) {
  if (loading) return <div className="border border-[#262629] rounded-[8px] bg-[#17171a] p-3"><LoadingState label="Loading entity" /></div>;
  if (error) return <div className="border border-amber-900/30 rounded-[8px] bg-amber-950/20 mono text-[11px] p-3 text-amber-200/80">{error}</div>;
  if (!entity) return <EmptyState title="No entity selected" hint="Click a node in the network graph or select from search." icon="◯" />;

  const relEvents = events ?? [];
  const relAlerts = alerts ?? [];

  return (
    <AnimatePresence mode="wait">
      <motion.div key={entity.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.18 }} className="border border-[#262629] rounded-[8px] bg-[#17171a] overflow-hidden flex flex-col" role="region" aria-label={`Entity ${entity.id}`}>
        {/* IDENTITY */}
        <div className="px-3 py-2.5 border-b border-[#262629] bg-[#0e0e10]/50">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="mono text-[10px] tracking-widest text-[#8a8a90]">{entity.type.toUpperCase()} {entity.canonicalType ? `• ${entity.canonicalType}` : ""}</div>
              <div className="mono text-[12px] font-semibold text-[#e8e8ea] tracking-wide">{entity.id}</div>
              <div className="text-[13px] font-medium text-[#d4d4d8] mt-0.5">{entity.displayName}</div>
            </div>
            <div className="text-right">
              <Badge tone="accent" aria-label={`Extraction confidence ${Math.round(entity.confidence*100)} percent`}>{Math.round(entity.confidence * 100)}% confidence</Badge>
              <div className="mono text-[10px] text-[#6b6b70] mt-1">extraction confidence</div>
            </div>
          </div>
        </div>

        {/* RELATIONSHIPS + SOURCES summary */}
        <div className="grid grid-cols-3 gap-0 border-b border-[#262629]">
          <div className="px-3 py-2 border-r border-[#262629]">
            <div className="mono text-[10px] text-[#6b6b70]">RELATIONSHIPS</div>
            <div className="mono text-[13px] text-[#e8e8ea]">{entity.relationshipCount}</div>
          </div>
          <div className="px-3 py-2 border-r border-[#262629]">
            <div className="mono text-[10px] text-[#6b6b70]">SOURCES</div>
            <div className="mono text-[13px] text-[#e8e8ea]">{entity.sourceCount}</div>
          </div>
          <div className="px-3 py-2">
            <div className="mono text-[10px] text-[#6b6b70]">LAST OBSERVED</div>
            <div className="mono text-[11px] text-[#d4d4d8] leading-tight">{entity.lastObserved}</div>
          </div>
        </div>

        {/* CASES */}
        <div className="px-3 py-2 border-b border-[#262629]">
          <div className="mono text-[10px] tracking-wide text-[#6b6b70] mb-1">CASES</div>
          {entity.associatedCases.length ? <div className="flex flex-wrap gap-1">{entity.associatedCases.map(c => <Badge key={c}>{c}</Badge>)}</div> : <span className="mono text-[11px] text-[#6b6b70]">No associated cases</span>}
        </div>

        {/* RELATIONSHIPS */}
        <div className="px-3 py-2 border-b border-[#262629]">
          <div className="mono text-[10px] tracking-wide text-[#6b6b70] mb-1.5">RELATIONSHIPS ({relationships.length})</div>
          {relationships.length === 0 ? <span className="mono text-[11px] text-[#6b6b70]">No relationships observed</span> : (
            <div className="space-y-1 max-h-[160px] overflow-auto pr-1">
              {relationships.map(r => {
                const other = r.source === entity.id ? r.target : r.source;
                return (
                  <button key={r.id} onClick={() => onSelectRelated?.(other)} className="w-full text-left flex items-center justify-between mono text-[11px] px-2 py-1.5 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22] hover:border-[#2e2e32] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]" aria-label={`Relationship ${r.type} to ${other}`}>
                    <span className="text-[#a1a1aa] truncate">{r.source} <span className="text-[#6b6b70]">→</span> {r.target}</span>
                    <span className="ml-2 shrink-0 mono text-[10px] px-1 py-0 rounded border border-[#262629] text-[#8a8a90]">{r.type}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* SOURCES */}
        <div className="px-3 py-2 border-b border-[#262629]">
          <div className="mono text-[10px] tracking-wide text-[#6b6b70] mb-1">SOURCES</div>
          <div className="flex flex-wrap gap-1">
            {Array.from(new Set(relationships.map(r=>r.sourceId))).slice(0,6).map(s => <span key={s} className="mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">{s}</span>)}
            {relationships.length===0 && <span className="mono text-[11px] text-[#6b6b70]">No source references</span>}
          </div>
        </div>

        {/* ACTIVITY */}
        {(relEvents.length > 0 || relAlerts.length > 0) && (
          <div className="px-3 py-2 border-b border-[#262629]">
            <div className="mono text-[10px] tracking-wide text-[#6b6b70] mb-1">ACTIVITY</div>
            {relEvents.slice(0,3).map(ev => <div key={ev.id} className="mono text-[11px] text-[#a1a1aa] truncate">• {ev.timestamp} — {ev.eventType} ({ev.source})</div>)}
            {relAlerts.slice(0,2).map(a => <div key={a.id} className="mono text-[11px] text-amber-200/60 truncate">⚑ {a.title} — {a.severity}</div>)}
            {relEvents.length===0 && relAlerts.length===0 && <span className="mono text-[11px] text-[#6b6b70]">No recent activity</span>}
          </div>
        )}

        {/* METADATA */}
        <div className="px-3 py-2 bg-[#0e0e10]/30">
          <div className="mono text-[10px] tracking-wide text-[#6b6b70] mb-1">METADATA</div>
          {Object.keys(entity.metadata).length ? (
            <div className="grid grid-cols-2 gap-1 mono text-[11px]">
              {Object.entries(entity.metadata).map(([k,v]) => <div key={k} className="flex gap-1"><span className="text-[#6b6b70]">{k}:</span><span className="text-[#a1a1aa] truncate">{v}</span></div>)}
            </div>
          ) : <span className="mono text-[11px] text-[#6b6b70]">No metadata</span>}
        </div>

        <div className="px-3 py-2 border-t border-[#262629] bg-[#0e0e10]/30 flex gap-1">
          {onStartInvestigation && <button onClick={()=> onStartInvestigation(entity.id)} aria-label={`Start investigation from ${entity.id}`} className="flex-1 mono text-[11px] px-2 py-1.5 rounded-[6px] bg-[#1e1e22] border border-[#262629] text-[#d4d4d8] hover:bg-[#262629] hover:border-[#2e2e32] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">Start investigation</button>}
          {onExplain && <button onClick={()=> onExplain(entity.id)} aria-label={`Explain ${entity.id}`} className="mono text-[11px] px-2 py-1.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] hover:border-[#2e2e32] hover:text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">Explain</button>}
        </div>
        <div className="px-3 py-1.5 mono text-[10px] text-[#6b6b70] border-t border-[#262629] bg-[#0e0e10]/30">Confidence = analytical extraction confidence • not guilt/criminality</div>
      </motion.div>
    </AnimatePresence>
  );
}
