import React, { useState } from "react";
import { motion } from "framer-motion";
import { TimelineEvent } from "../../types";
import { EmptyState } from "../ui/EmptyState";
import { LoadingState } from "../ui/LoadingState";

export function InvestigationTimeline({ events, onSelect, loading }: { events: TimelineEvent[]; onSelect?: (id: string) => void; loading?: boolean }) {
  const [filter, setFilter] = useState<string>("All");
  const [expanded, setExpanded] = useState<string | null>(null);
  const types = ["All", ...Array.from(new Set(events.map(e => e.eventType)))];
  const filtered = filter === "All" ? events : events.filter(e => e.eventType === filter);

  if (loading) return <div className="border border-[#1e1e22] rounded-[8px] bg-[#111113]"><LoadingState label="Loading timeline" /></div>;
  if (events.length === 0) return <EmptyState title="No timeline events" hint="No activity recorded for this context. Select a case or entity." />;

  return (
    <div className="border border-[#1e1e22] rounded-[8px] bg-[#111113] overflow-hidden flex flex-col" role="region" aria-label="Investigation timeline">
      <div className="px-3 py-2.5 border-b border-[#1e1e22] bg-[#0f0f11] flex items-center justify-between gap-2 flex-wrap">
        <div className="text-[11px] font-semibold tracking-[0.06em] text-[#a1a1aa]">INVESTIGATION TIMELINE</div>
        <div className="flex gap-1" role="tablist" aria-label="Filter timeline">
          {types.map(t => (
            <button key={t} role="tab" aria-selected={filter===t} onClick={() => setFilter(t)} className={`mono text-[10px] px-1.5 py-0.5 rounded-[6px] border focus:outline-none focus:ring-1 focus:ring-[#3a3a3e] ${filter===t ? "bg-[#1e1e22] border-[#2e2e32] text-[#e8e8ea]" : "border-transparent text-[#6b6b70] hover:text-[#a1a1aa]"}`}>{t}</button>
          ))}
        </div>
      </div>
      {filtered.length===0 ? <div className="p-4"><EmptyState title="No events for filter" hint={`No ${filter} events.`} /></div> : (
      <div className="flex-1 overflow-auto divide-y divide-[#1e1e22]" role="list">
        {filtered.map((ev, idx) => (
          <motion.div key={ev.id} role="listitem" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.02, duration: 0.18 }} onClick={() => { setExpanded(expanded===ev.id ? null : ev.id); onSelect?.(ev.id); }} className={`px-3 py-2.5 hover:bg-[#1a1a1e] cursor-pointer transition-colors focus:outline-none focus:bg-[#1a1a1e] ${expanded===ev.id ? "bg-[#1a1a1e]" : ""}`} tabIndex={0} onKeyDown={e=>{ if(e.key==="Enter") setExpanded(expanded===ev.id?null:ev.id); }} aria-expanded={expanded===ev.id}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="mono text-[10px] px-1 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">{ev.eventType}</span>
                  <span className="mono text-[11px] text-[#d4d4d8]">{ev.timestamp}</span>
                  <span className="mono text-[10px] text-[#6b6b70]">• {ev.source}</span>
                </div>
                <div className="mono text-[11px] text-[#a1a1aa] mt-1 truncate">{ev.description}</div>
                <div className="flex gap-1 mt-1 flex-wrap">
                  {ev.entities.map(e => <span key={e} className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22] text-[#8a8a90]">{e}</span>)}
                </div>
              </div>
              <span className="mono text-[10px] text-[#6b6b70] shrink-0" aria-label={`Confidence ${Math.round(ev.confidence*100)} percent`}>{Math.round(ev.confidence*100)}%</span>
            </div>
            {expanded===ev.id && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-2 mono text-[11px] text-[#8a8a90] border-t border-[#1e1e22] pt-2">
                Entities: {ev.entities.join(", ")} • Source {ev.source} • Confidence {ev.confidence} (extraction)
              </motion.div>
            )}
          </motion.div>
        ))}
      </div>
      )}
    </div>
  );
}
