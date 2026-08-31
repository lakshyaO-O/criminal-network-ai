import React from "react";

export function TopBar({ onSearchFocus, query, setQuery, caseId, apiStatus }: {
  onSearchFocus: () => void; query: string; setQuery: (v: string) => void;
  caseId?: string; apiStatus?: { label: string; ok: boolean; isMock?: boolean };
}) {
  return (
    <header className="h-[48px] shrink-0 flex items-center gap-3 px-4 border-b border-[#1e1e22] bg-[#0a0a0c] sticky top-0 z-30" role="banner">
      {/* LEFT — Product identity */}
      <div className="flex items-center gap-3 min-w-0 shrink-0">
        <div className="w-8 h-8 rounded-[7px] bg-[#17171a] border border-[#262629] flex items-center justify-center" aria-hidden>
          <span className="text-[13px] leading-none">⬢</span>
        </div>
        <div className="leading-tight min-w-0">
          <div className="text-[12px] font-semibold tracking-[0.12em] text-[#e8e8ea] whitespace-nowrap">CRIMINAL NETWORK ANALYSIS</div>
          <div className="text-[11px] text-[#8a8a90] font-normal -mt-0.5">Investigator Workspace</div>
        </div>
        <div className="hidden lg:block w-px h-7 bg-[#1e1e22] mx-2" aria-hidden />
        <div className="hidden lg:flex flex-col leading-tight">
          <span className="text-[10px] tracking-[0.08em] text-[#6b6b70] font-medium">NETWORK CONSOLE</span>
          <span className="mono text-[10px] text-[#8a8a90]">{caseId ?? "—"}</span>
        </div>
      </div>

      {/* CENTER — Global Search */}
      <div className="flex-1 flex justify-center px-6 max-w-[520px] mx-auto">
        <div className="w-full relative group">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[12px] text-[#6b6b70] pointer-events-none" aria-hidden>⌕</span>
          <input
            id="global-search"
            aria-label="Global search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onFocus={onSearchFocus}
            placeholder="Search entities, cases, relationships..."
            className="w-full h-[32px] pl-8 pr-3 text-[13px] bg-[#111113] border border-[#262629] rounded-[8px] placeholder:text-[#6b6b70] focus:outline-none focus:border-[#2e2e32] focus:bg-[#17171a] focus:ring-1 focus:ring-[#2a2a2e]"
          />
          <span className="absolute right-2 top-1/2 -translate-y-1/2 hidden sm:flex mono text-[10px] text-[#6b6b70] border border-[#1e1e22] rounded px-1 py-0 bg-[#0a0a0c]">/</span>
        </div>
      </div>

      {/* RIGHT — Status */}
      <div className="flex items-center gap-2.5 shrink-0">
        <div className="hidden md:flex items-center gap-2 pl-2.5 pr-3 py-1 rounded-full bg-[#111113] border border-[#1e1e22]">
          <span className={`w-1.5 h-1.5 rounded-full ${apiStatus?.ok ? "bg-emerald-500" : apiStatus?.isMock ? "bg-sky-500" : "bg-amber-500"} ${apiStatus?.ok ? "shadow-[0_0_6px_rgba(16,185,129,0.4)]" : ""}`} aria-hidden />
          <span className="text-[11px] font-medium text-[#a1a1aa]">{apiStatus?.label ?? "Checking…"}</span>
        </div>
        <div className="hidden sm:flex flex-col items-end leading-tight mr-1">
          <span className="text-[10px] tracking-[0.06em] text-[#6b6b70] font-medium">CASE</span>
          <span className="mono text-[11px] text-[#d4d4d8]">{caseId ?? "—"}</span>
        </div>
        <div className="w-8 h-8 rounded-full bg-[#1a1a1e] border border-[#262629] flex items-center justify-center text-[11px] font-medium text-[#d4d4d8]" aria-label="Investigator profile">IN</div>
      </div>
    </header>
  );
}
