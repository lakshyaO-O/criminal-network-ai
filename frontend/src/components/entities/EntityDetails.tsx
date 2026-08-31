import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Entity, Relationship, TimelineEvent, Alert } from "../../types";
import { Badge } from "../ui/Badge";
import { EmptyState } from "../ui/EmptyState";
import { LoadingState } from "../ui/LoadingState";

export function EntityDetails({ entity, relationships, events, alerts, onSelectRelated, onStartInvestigation, onExplain, loading, error }: {
  entity: Entity | null; relationships: Relationship[]; events?: TimelineEvent[]; alerts?: Alert[]; onSelectRelated?: (id: string) => void; onStartInvestigation?: (id: string) => void; onExplain?: (id: string) => void; loading?: boolean; error?: string | null;
}) {
  if (loading) return <div className="border border-[#1e1e22] rounded-[8px] bg-[#111113] p-3"><LoadingState label="Loading entity" /></div>;
  if (error) return <div className="border border-amber-900/20 rounded-[8px] bg-amber-950/10 text-[13px] p-3 text-amber-200/80">{error}</div>;
  if (!entity) return <EmptyState title="No entity selected" hint="Click a node in the network graph or select from search." icon="◯" />;

  const relEvents = events ?? [];
  const relAlerts = alerts ?? [];

  return (
    <AnimatePresence mode="wait">
      <motion.div key={entity.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.18 }} className="border border-[#1e1e22] rounded-[8px] bg-[#111113] overflow-hidden flex flex-col" role="region" aria-label={`Entity ${entity.id}`}>
        {/* IDENTITY — dominant */}
        <div className="px-4 py-3 border-b border-[#1e1e22] bg-[#0f0f11]">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[11px] tracking-[0.08em] font-semibold text-[#8a8a90]">{entity.type.toUpperCase()} {entity.canonicalType ? `• ${entity.canonicalType}` : ""}</div>
              <div className="mono text-[12px] font-medium text-[#e8e8ea] mt-0.5 tracking-wide">{entity.id}</div>
              <div className="text-[15px] font-semibold text-[#f4f4f5] mt-1 leading-tight">{entity.displayName}</div>
            </div>
            <div className="text-right shrink-0">
              <Badge tone="accent" aria-label={`Extraction confidence ${Math.round(entity.confidence*100)} percent`}>{Math.round(entity.confidence * 100)}% confidence</Badge>
              <div className="mono text-[10px] text-[#6b6b70] mt-1">extraction confidence</div>
            </div>
          </div>
        </div>

        {/* Stats — subtle separator, not card */}
        <div className="grid grid-cols-3 divide-x divide-[#1e1e22] border-y border-[#1e1e22] bg-[#0f0f11]">
          <div className="px-4 py-2.5">
            <div className="text-[10px] tracking-[0.08em] font-medium text-[#6b6b70]">RELATIONSHIPS</div>
            <div className="text-[15px] font-semibold text-[#e8e8ea] mono">{entity.relationshipCount}</div>
          </div>
          <div className="px-4 py-2.5">
            <div className="text-[10px] tracking-[0.08em] font-medium text-[#6b6b70]">SOURCES</div>
            <div className="text-[15px] font-semibold text-[#e8e8ea] mono">{entity.sourceCount}</div>
          </div>
          <div className="px-4 py-2.5">
            <div className="text-[10px] tracking-[0.08em] font-medium text-[#6b6b70]">LAST OBSERVED</div>
            <div className="mono text-[11px] font-medium text-[#d4d4d8] leading-tight mt-0.5">{entity.lastObserved}</div>
          </div>
        </div>

        {/* CASES */}
        <div className="px-4 py-2.5">
          <div className="text-[10px] tracking-[0.08em] font-semibold text-[#6b6b70] mb-1.5">CASES</div>
          {entity.associatedCases.length ? <div className="flex flex-wrap gap-1.5">{entity.associatedCases.map(c => <Badge key={c}>{c}</Badge>)}</div> : <span className="text-[13px] text-[#6b6b70]">No associated cases</span>}
        </div>

        {/* RELATIONSHIPS — scannable */}
        <div className="px-4 py-3 border-t border-[#1e1e22]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] tracking-[0.06em] font-semibold text-[#a1a1aa]">RELATIONSHIPS</span>
            <span className="mono text-[11px] text-[#6b6b70]">{relationships.length}</span>
          </div>
          {relationships.length === 0 ? <span className="text-[13px] text-[#6b6b70]">No relationships observed for this entity.</span> : (
            <div className="space-y-1 max-h-[180px] overflow-auto pr-1">
              {relationships.map(r => {
                const other = r.source === entity.id ? r.target : r.source;
                return (
                  <button key={r.id} onClick={() => onSelectRelated?.(other)} className="w-full text-left flex items-center gap-2 px-2.5 py-2 rounded-[6px] bg-[#0a0a0c] border border-[#1e1e22] hover:border-[#262629] hover:bg-[#111113] focus:outline-none focus:ring-1 focus:ring-[#2a2a2e]" aria-label={`Relationship ${r.type} to ${other}`}>
                    <span className="mono text-[11px] text-[#8a8a90] truncate flex-1">{r.source} <span className="text-[#6b6b70] mx-1">→</span> {r.target}</span>
                    <span className="shrink-0 mono text-[10px] px-1.5 py-0.5 rounded bg-[#17171a] border border-[#262629] text-[#a1a1aa]">{r.type}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* SOURCES */}
        <div className="px-4 py-2.5 border-t border-[#1e1e22] bg-[#0f0f11]/50">
          <div className="text-[10px] tracking-[0.08em] font-semibold text-[#6b6b70] mb-1.5">SOURCES</div>
          <div className="flex flex-wrap gap-1.5">
            {Array.from(new Set(relationships.map(r=>r.sourceId))).slice(0,6).map(s => <span key={s} className="mono text-[11px] px-2 py-1 rounded-[6px] bg-[#0a0a0c] border border-[#1e1e22] text-[#8a8a90]">{s}</span>)}
            {relationships.length===0 && <span className="text-[13px] text-[#6b6b70]">No source references</span>}
          </div>
        </div>

        {/* ACTIVITY */}
        {(relEvents.length > 0 || relAlerts.length > 0) && (
          <div className="px-4 py-3 border-t border-[#1e1e22]">
            <div className="text-[11px] tracking-[0.06em] font-semibold text-[#a1a1aa] mb-2">ACTIVITY</div>
            {relEvents.slice(0,3).map(ev => <div key={ev.id} className="flex gap-2 text-[13px] leading-snug"><span className="mono text-[11px] text-[#6b6b70] shrink-0">{ev.timestamp.slice(0,16)}</span><span className="text-[#a1a1aa] truncate">{ev.eventType} • {ev.source}</span></div>)}
            {relAlerts.slice(0,2).map(a => <div key={a.id} className="text-[13px] text-amber-200/70 mt-1">⚑ {a.title} — <span className="mono text-[11px]">{a.severity}</span></div>)}
          </div>
        )}

        {/* METADATA */}
        <div className="px-4 py-3 border-t border-[#1e1e22] bg-[#0a0a0c]/50">
          <div className="text-[10px] tracking-[0.08em] font-semibold text-[#6b6b70] mb-2">METADATA</div>
          {Object.keys(entity.metadata).length ? (
            <div className="grid grid-cols-2 gap-x-3 gap-y-1">
              {Object.entries(entity.metadata).map(([k,v]) => <div key={k} className="flex gap-1.5 text-[13px]"><span className="text-[#6b6b70]">{k}:</span><span className="mono text-[11px] text-[#a1a1aa] truncate">{String(v)}</span></div>)}
            </div>
          ) : <span className="text-[13px] text-[#6b6b70]">No metadata</span>}
        </div>

        <div className="px-4 py-3 border-t border-[#1e1e22] bg-[#0f0f11] flex gap-2">
          {onStartInvestigation && <button onClick={()=> onStartInvestigation(entity.id)} aria-label={`Start investigation from ${entity.id}`} className="flex-1 text-[13px] font-medium px-3 py-2 rounded-[6px] bg-[#e8e8ea] text-[#0a0a0c] hover:bg-white focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">Start investigation</button>}
          {onExplain && <button onClick={()=> onExplain(entity.id)} aria-label={`Explain ${entity.id}`} className="text-[13px] px-3 py-2 rounded-[6px] bg-[#0a0a0c] border border-[#262629] text-[#a1a1aa] hover:border-[#2e2e32] hover:text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#2a2a2e]">Explain</button>}
        </div>
        <div className="px-4 py-2 mono text-[11px] text-[#6b6b70] border-t border-[#1e1e22] bg-[#0a0a0c]">Analytical confidence • Not guilt determination</div>
      </motion.div>
    </AnimatePresence>
  );
}
