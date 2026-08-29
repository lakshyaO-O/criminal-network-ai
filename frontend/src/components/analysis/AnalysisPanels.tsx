import React from "react";
import { LoadingState } from "../ui/LoadingState";
import { EmptyState } from "../ui/EmptyState";
import { ErrorState } from "../ui/ErrorState";

function Section({ title, children, count, onExplain }: { title: string; children: React.ReactNode; count?: number; onExplain?: () => void }) {
  return (
    <div className="border border-[#262629] rounded-[8px] bg-[#17171a] overflow-hidden">
      <div className="px-3 py-2 border-b border-[#262629] flex justify-between items-center gap-2">
        <span className="mono text-[11px] font-semibold tracking-wide text-[#d4d4d8]">{title}</span>
        <span className="flex items-center gap-1">
          {onExplain && <button onClick={onExplain} aria-label={`Explain ${title}`} className="mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#1e1e22] border border-[#262629] text-[#8a8a90] hover:border-[#2e2e32] hover:text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">Explain</button>}
          {count !== undefined && <span className="mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">{count}</span>}
        </span>
      </div>
      <div className="px-3 py-2">{children}</div>
    </div>
  );
}

export function NetworkMetrics({ centrality, loading, error, onExplain }: { centrality: { centrality: Record<string, Record<string, number>>; explanations: Record<string, string> } | null; loading: boolean; error: string | null; onExplain?: () => void }) {
  if (loading) return <Section title="NETWORK METRICS" onExplain={onExplain}><LoadingState label="Loading metrics" /></Section>;
  if (error) return <Section title="NETWORK METRICS" onExplain={onExplain}><ErrorState title="Metrics unavailable" message={error} /></Section>;
  if (!centrality) return <Section title="NETWORK METRICS" onExplain={onExplain}><EmptyState title="No metrics" hint="Run analysis to populate." /></Section>;
  const top = Object.entries(centrality.centrality.degree || {}).sort((a,b)=>b[1]-a[1]).slice(0,5);
  return (
    <Section title="NETWORK METRICS" onExplain={onExplain}>
      <div className="mono text-[10px] text-[#6b6b70] mb-2">Degree • Betweenness • Closeness • PageRank — analytical, not guilt</div>
      <div className="space-y-1">
        {top.map(([id, deg]) => (
          <div key={id} className="flex justify-between mono text-[11px] px-2 py-1 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22]">
            <span className="text-[#d4d4d8]">{id}</span>
            <span className="text-[#8a8a90]">deg {deg.toFixed(3)} • bet {(centrality.centrality.betweenness[id]||0).toFixed(3)}</span>
          </div>
        ))}
      </div>
    </Section>
  );
}

export function CommunitiesPanel({ data, loading, error, onExplain }: { data: { communities: { community_id: string; members: string[]; size: number; internal_edges: number; density: number }[] } | null; loading: boolean; error: string | null; onExplain?: () => void }) {
  if (loading) return <Section title="COMMUNITIES" onExplain={onExplain}><LoadingState label="Loading communities" /></Section>;
  if (error) return <Section title="COMMUNITIES" onExplain={onExplain}><ErrorState title="Unavailable" message={error} /></Section>;
  if (!data || data.communities.length===0) return <Section title="COMMUNITIES" onExplain={onExplain}><EmptyState title="No communities" /></Section>;
  return (
    <Section title="COMMUNITIES" count={data.communities.length} onExplain={onExplain}>
      <div className="space-y-1.5">
        {data.communities.slice(0,6).map(c => (
          <div key={c.community_id} className="px-2 py-1.5 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22] mono">
            <div className="flex justify-between text-[11px]"><span className="text-[#d4d4d8]">{c.community_id}</span><span className="text-[#8a8a90]">{c.size} members • dens {c.density.toFixed(2)}</span></div>
            <div className="text-[10px] text-[#6b6b70] truncate mt-0.5">{c.members.slice(0,5).join(", ")}{c.members.length>5?" …":""}</div>
          </div>
        ))}
      </div>
    </Section>
  );
}

export function BridgesPanel({ data, loading, error, onSelect, onExplain }: { data: { bridges: { entity_id: string; entity_type: string; metric: string; score: number; explanation: string }[] } | null; loading: boolean; error: string | null; onSelect: (id:string)=>void; onExplain?: () => void }) {
  if (loading) return <Section title="BRIDGE CANDIDATES" onExplain={onExplain}><LoadingState label="Loading bridges" /></Section>;
  if (error) return <Section title="BRIDGE CANDIDATES" onExplain={onExplain}><ErrorState title="Unavailable" message={error} /></Section>;
  if (!data || data.bridges.length===0) return <Section title="BRIDGE CANDIDATES" onExplain={onExplain}><EmptyState title="No bridge candidates" /></Section>;
  return (
    <Section title="BRIDGE CANDIDATES" count={data.bridges.length} onExplain={onExplain}>
      <div className="space-y-1">
        {data.bridges.slice(0,6).map(b => (
          <button key={b.entity_id} onClick={()=>onSelect(b.entity_id)} className="w-full text-left px-2 py-1.5 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22] hover:border-[#2e2e32] mono">
            <div className="flex justify-between text-[11px]"><span className="text-[#d4d4d8]">{b.entity_id} <span className="text-[#6b6b70]">({b.entity_type})</span></span><span className="text-[#8a8a90]">{b.score.toFixed(3)}</span></div>
            <div className="text-[10px] text-[#8a8a90] leading-snug mt-0.5 line-clamp-2">{b.explanation}</div>
          </button>
        ))}
      </div>
    </Section>
  );
}

export function TemporalPanel({ data, loading, error, onExplain }: { data: { temporal_indicators: { time_window: string; observed_count: number; baseline: { mean:number; std:number; threshold:number }; explanation: string; entity_ids: string[] }[] } | null; loading: boolean; error: string | null; onExplain?: () => void }) {
  if (loading) return <Section title="TEMPORAL SIGNALS" onExplain={onExplain}><LoadingState label="Loading temporal" /></Section>;
  if (error) return <Section title="TEMPORAL SIGNALS" onExplain={onExplain}><ErrorState title="Unavailable" message={error} /></Section>;
  if (!data || data.temporal_indicators.length===0) return <Section title="TEMPORAL SIGNALS" onExplain={onExplain}><EmptyState title="No temporal bursts" /></Section>;
  return (
    <Section title="TEMPORAL SIGNALS" count={data.temporal_indicators.length} onExplain={onExplain}>
      <div className="space-y-1">
        {data.temporal_indicators.slice(0,5).map((t,i)=> (
          <div key={i} className="px-2 py-1.5 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22] mono text-[11px]">
            <div className="text-[#d4d4d8] truncate">{t.time_window}</div>
            <div className="text-[#8a8a90]">obs {t.observed_count} • base {t.baseline.mean.toFixed(1)}±{t.baseline.std.toFixed(1)} thr {t.baseline.threshold.toFixed(1)}</div>
            <div className="text-[10px] text-[#6b6b70] leading-snug line-clamp-2">{t.explanation}</div>
          </div>
        ))}
      </div>
    </Section>
  );
}

export function ChainsPanel({ data, loading, error, onExplain }: { data: { transaction_chains: { chain_id: string; source_account: string; intermediate_accounts: string[]; destination_account: string; hop_count: number; explanation: string }[] } | null; loading: boolean; error: string | null; onExplain?: () => void }) {
  if (loading) return <Section title="TRANSACTION CHAINS" onExplain={onExplain}><LoadingState label="Loading chains" /></Section>;
  if (error) return <Section title="TRANSACTION CHAINS" onExplain={onExplain}><ErrorState title="Unavailable" message={error} /></Section>;
  if (!data || data.transaction_chains.length===0) return <Section title="TRANSACTION CHAINS" onExplain={onExplain}><EmptyState title="No chains" /></Section>;
  return (
    <Section title="TRANSACTION CHAINS" count={data.transaction_chains.length} onExplain={onExplain}>
      <div className="space-y-1">
        {data.transaction_chains.slice(0,5).map(c=> (
          <div key={c.chain_id} className="px-2 py-1.5 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22] mono text-[11px]">
            <div className="text-[#d4d4d8] truncate">{c.source_account} → {c.intermediate_accounts.join(" → ")}{c.intermediate_accounts.length?" → ":""}{c.destination_account} <span className="text-[#6b6b70]">({c.hop_count} hops)</span></div>
            <div className="text-[10px] text-[#6b6b70] line-clamp-2">{c.explanation}</div>
          </div>
        ))}
      </div>
    </Section>
  );
}

export function IndicatorsPanel({ data, loading, error, onSelect, onExplain }: { data: { indicators: { indicator_id: string; indicator_type: string; severity: string; entity_ids: string[]; score: number; explanation: string; evidence: string[] }[] } | null; loading: boolean; error: string | null; onSelect: (id:string)=>void; onExplain?: () => void }) {
  if (loading) return <Section title="INDICATORS" onExplain={onExplain}><LoadingState label="Loading indicators" /></Section>;
  if (error) return <Section title="INDICATORS" onExplain={onExplain}><ErrorState title="Unavailable" message={error} /></Section>;
  if (!data || data.indicators.length===0) return <Section title="INDICATORS" onExplain={onExplain}><EmptyState title="No indicators" /></Section>;
  return (
    <Section title="INDICATORS" count={data.indicators.length} onExplain={onExplain}>
      <div className="space-y-1">
        {data.indicators.slice(0,6).map(ind=> (
          <button key={ind.indicator_id} onClick={()=> ind.entity_ids[0] && onSelect(ind.entity_ids[0])} className="w-full text-left px-2 py-1.5 rounded-[6px] bg-[#0e0e10] border border-[#1e1e22] hover:border-[#2e2e32] mono">
            <div className="flex justify-between text-[11px]"><span className="text-[#d4d4d8]">{ind.indicator_type}</span><span className={`text-[10px] px-1 rounded border ${ind.severity==="HIGH"?"border-amber-500/20 text-amber-200/80":"border-[#262629] text-[#8a8a90]"}`}>{ind.severity}</span></div>
            <div className="text-[11px] text-[#8a8a90] leading-snug line-clamp-2">{ind.explanation}</div>
            <div className="text-[10px] text-[#6b6b70] mt-0.5">score {ind.score.toFixed(2)} • {ind.entity_ids.join(", ")}</div>
          </button>
        ))}
      </div>
    </Section>
  );
}
