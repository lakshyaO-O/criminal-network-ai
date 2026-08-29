import React, { useState } from "react";
import type { ProvenanceEntry } from "../../types";

export function ProvenancePanel({ provenance }: { provenance: ProvenanceEntry[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!provenance || provenance.length===0) return <div className="mono text-[10px] text-[#6b6b70]">No provenance entries</div>;
  const shown = expanded ? provenance : provenance.slice(0,2);
  return (
    <div className="border border-[#1e1e22] rounded-[6px] bg-[#0e0e10] overflow-hidden">
      <button onClick={()=> setExpanded(!expanded)} aria-expanded={expanded} className="w-full flex justify-between items-center px-2 py-1.5 mono text-[10px] text-[#8a8a90] hover:text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">
        <span>PROVENANCE • {provenance.length} entries</span>
        <span className="text-[10px]">{expanded ? "collapse" : "expand"}</span>
      </button>
      <div className="divide-y divide-[#1e1e22]">
        {shown.map((p, i)=> (
          <div key={i} className="px-2 py-1.5 mono text-[10px] leading-snug">
            <div className="flex gap-1.5 flex-wrap">
              <span className="px-1 py-0 rounded bg-[#17171a] border border-[#262629] text-[#8a8a90]">{String(p.source || "unknown")}</span>
              {p.analysis_type && <span className="text-[#6b6b70]">{String(p.analysis_type)}</span>}
              {p.timestamp && !isNaN(new Date(String(p.timestamp)).getTime()) && <span className="text-[#6b6b70]">{new Date(String(p.timestamp)).toLocaleString()}</span>}
            </div>
            {p.parameters && Object.keys(p.parameters as Record<string,unknown>).length>0 && (
              <div className="text-[#6b6b70] mt-1 truncate">params: {JSON.stringify(p.parameters as Record<string,unknown>).slice(0,120)}</div>
            )}
            {/* never display connection strings or secrets — filter if present */}
          </div>
        ))}
      </div>
    </div>
  );
}
