import React from "react";
import { motion } from "framer-motion";
import { Alert } from "../../types";
import { EmptyState } from "../ui/EmptyState";
import { LoadingState } from "../ui/LoadingState";

const severity: Record<string, string> = {
  low: "border-[#262629] text-[#8a8a90]",
  medium: "border-[#2e2e32] text-[#d4d4d8]",
  high: "border-[#3a3a2e] text-[#e8d8a0]"
};

export function AlertPanel({ alerts, onEntitySelect, loading }: { alerts: Alert[]; onEntitySelect: (id: string) => void; loading?: boolean }) {
  if (loading) return <div className="border border-[#262629] rounded-[8px] bg-[#17171a]"><LoadingState label="Loading indicators" /></div>;
  if (alerts.length===0) return <EmptyState title="No pattern indicators" hint="No unusual activity detected in current context." />;

  return (
    <div className="border border-[#262629] rounded-[8px] bg-[#17171a] overflow-hidden flex flex-col" role="region" aria-label="Pattern indicators">
      <div className="px-3 py-2 border-b border-[#262629] flex items-center justify-between">
        <div className="mono text-[11px] font-semibold tracking-wide text-[#d4d4d8]">PATTERN INDICATORS</div>
        <span className="mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]" aria-label={`${alerts.length} active indicators`}>{alerts.length} active</span>
      </div>
      <div className="flex-1 overflow-auto divide-y divide-[#1e1e22]" role="list">
        {alerts.map((a, idx) => (
          <motion.div key={a.id} role="listitem" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: idx * 0.03, duration: 0.18 }} onClick={() => onEntitySelect(a.entityId)} tabIndex={0} onKeyDown={e=>{ if(e.key==="Enter") onEntitySelect(a.entityId); }} className={`px-3 py-2.5 hover:bg-[#1a1a1e] cursor-pointer border-l-2 focus:outline-none focus:bg-[#1a1a1e] ${severity[a.severity]}`}>
            <div className="flex items-center gap-1.5">
              <span className="mono text-[10px] tracking-wide text-[#8a8a90]">{a.indicator}</span>
              <span className={`mono text-[9px] px-1 py-0 rounded border ${a.severity==="high" ? "bg-amber-500/10 border-amber-500/20 text-amber-200/80" : a.severity==="medium" ? "bg-zinc-700/20 border-zinc-700/30 text-zinc-300" : "bg-zinc-800/20 border-zinc-800 text-zinc-400"}`} aria-label={`Severity ${a.severity}`}>{a.severity.toUpperCase()}</span>
            </div>
            <div className="mono text-[11px] font-medium text-[#d4d4d8] mt-1">{a.title}</div>
            <div className="mono text-[11px] text-[#8a8a90] mt-1 leading-snug">{a.reason}</div>
            <div className="flex gap-1 mt-1.5 flex-wrap">
              {a.evidence.map(e => <span key={e} className="mono text-[10px] px-1 py-0 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22] text-[#6b6b70]">{e}</span>)}
            </div>
            <div className="mono text-[10px] text-[#6b6b70] mt-1">{a.timestamp} • {a.entityId}</div>
          </motion.div>
        ))}
      </div>
      <div className="px-3 py-1.5 mono text-[10px] text-[#6b6b70] border-t border-[#262629] bg-[#0e0e10]/30">Descriptive indicators only • not criminality judgments</div>
    </div>
  );
}
