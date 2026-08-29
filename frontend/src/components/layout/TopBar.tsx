import React from "react";
import { ConnectionStatus } from "../ui/ErrorState";

export function TopBar({ onSearchFocus, query, setQuery }: { onSearchFocus: () => void; query: string; setQuery: (v: string) => void }) {
  return (
    <header className="h-[44px] shrink-0 flex items-center gap-3 px-3 border-b border-[#262629] bg-[#0e0e10] sticky top-0 z-30" role="banner">
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="w-7 h-7 rounded-[6px] bg-[#1a1a1e] border border-[#262629] flex items-center justify-center mono text-[11px] font-semibold tracking-widest" aria-hidden>SIH</div>
        <div className="leading-tight">
          <div className="text-[12px] font-semibold tracking-[0.08em] text-[#e8e8ea]">26189 — Network Console</div>
          <div className="mono text-[10px] text-[#8a8a90]">Investigator workspace • synthetic demo</div>
        </div>
      </div>

      <div className="flex-1 flex justify-center px-4 max-w-[560px] mx-auto">
        <div className="w-full relative">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 mono text-[11px] text-[#8a8a90] pointer-events-none" aria-hidden>/</span>
          <input
            id="global-search"
            aria-label="Global search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onFocus={onSearchFocus}
            placeholder="Search PER-00042, CASE-00003, PHONE-00017, Location…"
            className="w-full h-[30px] pl-6 pr-3 mono text-[12px] bg-[#17171a] border border-[#262629] rounded-[8px] placeholder:text-[#6b6b70] focus:outline-none focus:border-[#2e2e32] focus:bg-[#1a1a1e] focus:ring-1 focus:ring-[#3a3a3e]"
          />
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <div className="hidden sm:flex"><ConnectionStatus online /></div>
        <div className="w-7 h-7 rounded-full bg-[#1e1e22] border border-[#262629] flex items-center justify-center mono text-[11px]" aria-label="Investigator profile">IN</div>
      </div>
    </header>
  );
}
