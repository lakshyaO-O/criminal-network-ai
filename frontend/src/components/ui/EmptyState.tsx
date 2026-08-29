import React from "react";
export function EmptyState({ title, hint, icon = "—" }: { title: string; hint?: string; icon?: string }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-8 text-center border border-dashed border-[#262629] rounded-[8px] bg-[#17171a]">
      <div className="w-7 h-7 rounded-[6px] border border-[#262629] bg-[#0e0e10] flex items-center justify-center mono text-[10px] text-[#6b6b70] mb-2" aria-hidden>{icon}</div>
      <div className="mono text-[11px] text-[#a1a1aa]">{title}</div>
      {hint && <div className="mono text-[10px] text-[#6b6b70] mt-1 max-w-[28ch]">{hint}</div>}
    </div>
  );
}
