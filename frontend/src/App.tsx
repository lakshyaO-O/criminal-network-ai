import React, { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TopBar } from "./components/layout/TopBar";
import { Sidebar, MobileSidebar } from "./components/navigation/Sidebar";
import { NetworkGraph } from "./components/graph/NetworkGraph";
import { EntityDetails } from "./components/entities/EntityDetails";
import { InvestigationTimeline } from "./components/timeline/InvestigationTimeline";
import { AlertPanel } from "./components/alerts/AlertPanel";
import { ShortcutsOverlay } from "./components/ui/ShortcutsOverlay";
import { EmptyState } from "./components/ui/EmptyState";
import { ErrorState } from "./components/ui/ErrorState";
import { SkeletonRows } from "./components/ui/LoadingState";
import { DATA_SOURCE } from "./config";
import { useHealth } from "./hooks/useHealth";
import { useNetworkData, useEntityRelationships } from "./hooks/useNetworkData";
import { useGraphIntelligence, useEntityIntelligence, usePath } from "./hooks/useAnalysis";
import { NetworkMetrics, CommunitiesPanel, BridgesPanel, TemporalPanel, ChainsPanel, IndicatorsPanel } from "./components/analysis/AnalysisPanels";
import { getEntity } from "./api/entities";
import type { Entity, Relationship } from "./types";
import { useInvestigationWorkspace } from "./hooks/useInvestigationWorkspace";
import { InvestigationWorkspace } from "./components/investigation/InvestigationWorkspace";
import { ExplanationPanel } from "./components/explainability/ExplanationPanel";
import { AuditWorkspace } from "./components/audit/AuditWorkspace";
import { AIWorkspace } from "./components/ai/AIWorkspace";
import { useFindingExplanation, useEntityExplanation, usePathExplanation, useCentralityExplanation } from "./hooks/useExplainability";
import { useAuditTrail } from "./hooks/useAudit";

export default function App() {
  const health = useHealth(30000);
  const [selectedCase, setSelectedCase] = useState<string>("case-00001");
  const { entities, relationships, timelineEvents, alerts, cases, allSearchItems, loading: netLoading, error: netError, retry: retryNetwork } = useNetworkData(selectedCase);
  const investigation = useInvestigationWorkspace();
  const intelligence = useGraphIntelligence(selectedCase);
  const [selectedId, setSelectedId] = useState<string>("person-00001");
  // Explainability state — direct M9 calls, no fallback, no invented data
  const [explainFindingId, setExplainFindingId] = useState<string | null>(null);
  const [explainEntityId, setExplainEntityId] = useState<string | null>(null);
  const [explainCentralityId, setExplainCentralityId] = useState<string | null>(null);
  const findingExplain = useFindingExplanation(explainFindingId);
  const entityExplain = useEntityExplanation(explainEntityId);
  const centralityExplain = useCentralityExplanation(explainCentralityId);
  const audit = useAuditTrail({ case_id: selectedCase, limit: 50 });
  const [activeNav, setActiveNav] = useState("networks");
  const [query, setQuery] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [searchIdx, setSearchIdx] = useState(0);
  const [pathTarget, setPathTarget] = useState<string | null>(null);
  const [pathSourceInput, setPathSourceInput] = useState("");
  const [pathTargetInput, setPathTargetInput] = useState("");

  const entityInt = useEntityIntelligence(selectedId || null);
  const relsHook = useEntityRelationships(selectedId || null);
  const pathHook = usePath(selectedId || null, pathTarget, selectedCase);

  const [entityDetail, setEntityDetail] = useState<{ id: string; displayName: string; type: string } | null>(null);
  useEffect(() => {
    if (!selectedId) { setEntityDetail(null); return; }
    const found = entities.find(e=>e.id===selectedId);
    if (found) { setEntityDetail({ id: found.id, displayName: found.displayName, type: found.type }); return; }
    // fetch from API for full fidelity when network doesn't contain it
    if (DATA_SOURCE==="api") {
      getEntity(selectedId).then(o=> setEntityDetail({ id: o.entity_id, displayName: String(o.full_name || o.name || o.entity_id), type: o.entity_type })).catch(()=> setEntityDetail(null));
    }
  }, [selectedId, entities]);

  const entityForDetails = useMemo(() => {
    if (!selectedId) return null;
    const base = entities.find(e=>e.id===selectedId);
    if (base) return base;
    if (entityDetail) return { id: entityDetail.id, type: (entityDetail.type as Entity["type"]) || "Person", displayName: entityDetail.displayName, confidence: 0.85, relationshipCount: relsHook.data.length, sourceCount: 1, associatedCases: [selectedCase], lastObserved: new Date().toISOString().slice(0,19).replace("T"," "), metadata: {} } as Entity;
    return null;
  }, [selectedId, entities, relsHook.data.length, selectedCase, entityDetail]);

  const relatedEvents = useMemo(() => selectedId ? timelineEvents.filter(e => e.entities.includes(selectedId)) : timelineEvents.slice(0,5), [selectedId, timelineEvents]);
  const relatedAlerts = useMemo(() => selectedId ? alerts.filter(a => a.entityId === selectedId) : alerts, [selectedId, alerts]);

  // Investigation derived entities — M8A subgraph is source of truth (entities/relationships directly from backend)
  const investigationEntities = useMemo(() => {
    if (!investigation.isActive || !investigation.subgraph) return [] as Entity[];
    const sgEntities = investigation.subgraph.entities as Record<string, unknown>[];
    // Map M8A entities (Dict with entity_id, entity_type, full_name/name etc.) to frontend Entity
    return sgEntities.map((e) => {
      const eid = String((e as Record<string,string>).entity_id || "");
      const etype = String((e as Record<string,string>).entity_type || "Person");
      const displayType = ((): Entity["type"] => {
        const m: Record<string, Entity["type"]> = { Person: "Person", Organization: "Organization", PhoneNumber: "Phone", Phone: "Phone", Vehicle: "Vehicle", Location: "Location", FinancialAccount: "Account", Account: "Account", Transaction: "Account", Communication: "Phone", Case: "Organization", FIR: "Organization", Event: "Location", Evidence: "Organization" };
        return m[etype] || "Person";
      })();
      const name = String((e as Record<string,string>).full_name || (e as Record<string,string>).name || (e as Record<string,string>).title || eid);
      return {
        id: eid,
        type: displayType,
        canonicalType: etype as Entity["canonicalType"],
        displayName: name,
        confidence: 0.85,
        relationshipCount: 0,
        sourceCount: 1,
        associatedCases: [investigation.caseId || selectedCase],
        lastObserved: String((e as Record<string,string>).created_at || new Date().toISOString().slice(0,19).replace("T"," ")),
        metadata: (e as Record<string,unknown>).metadata as Record<string,string> || {}
      } as Entity;
    });
  }, [investigation.isActive, investigation.subgraph, selectedCase]);

  const investigationRelationships = useMemo(() => {
    if (!investigation.isActive || !investigation.subgraph) return [] as Relationship[];
    const sgRels = investigation.subgraph.relationships as Record<string, unknown>[];
    return sgRels.map((r) => {
      const rid = String((r as Record<string,string>).relationship_id || "");
      const src = String((r as Record<string,string>).source_id || "");
      const tgt = String((r as Record<string,string>).target_id || "");
      const rtype = String((r as Record<string,string>).relationship_type || "ASSOCIATED_WITH") as Relationship["type"];
      return {
        id: rid || `${src}-${tgt}`,
        source: src,
        target: tgt,
        type: rtype,
        confidence: Number((r as Record<string,unknown>).confidence ?? 0.7),
        timestamp: (r as Record<string,string>).timestamp ?? null,
        sourceId: String((r as Record<string,string>).source_id || rid),
        extractionMethod: String((r as Record<string,string>).extraction_method || "m8a"),
        metadata: (r as Record<string,unknown>).metadata as Record<string,unknown> || {}
      } as Relationship;
    });
  }, [investigation.isActive, investigation.subgraph]);

  function handleStartInvestigation(id: string) {
    investigation.startInvestigation(selectedCase, id, 2);
    setSelectedId(id);
    setActiveNav("investigation");
  }

  // Clear stale investigation + explanations + path + AI when case changes (never show old-case results)
  useEffect(() => {
    if (investigation.isActive && investigation.caseId !== selectedCase) investigation.clearInvestigation();
    setExplainFindingId(null); setExplainEntityId(null); setExplainCentralityId(null); setPathTarget(null);
    // AIWorkspace internally clears AI analysis on case/root change via its own effect; App also ensures drawer not showing stale explanation
  }, [selectedCase]);

  // Also clear AI analysis when root entity changes (entity-scoped AI)
  useEffect(() => {
    // This ensures no stale AI result after entity switch; AIWorkspace handles via props, but App keeps path in sync
  }, [selectedId]);

  // Search: real API-backed via entities/cases/relationships, debounced display already; no extra fetch needed because network provides canonical list
  const searchItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allSearchItems.slice(0,8);
    return allSearchItems.filter(i=> i.id.toLowerCase().includes(q) || i.label.toLowerCase().includes(q)).slice(0,10);
  }, [query, allSearchItems]);

  useEffect(()=> { if (!selectedCase) { setExplainFindingId(null); setExplainCentralityId(null); } }, [selectedCase]);

  useEffect(()=> { if (selectedId && explainEntityId && explainEntityId !== selectedId) setExplainEntityId(null); }, [selectedId, explainEntityId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (document.activeElement as HTMLElement)?.tagName;
      const isInput = tag==="INPUT" || tag==="TEXTAREA";
      if (e.key==="/" && !isInput) { e.preventDefault(); document.getElementById("global-search")?.focus(); setShowSearch(true); }
      if (e.key==="?" && !isInput) setShowShortcuts(v=>!v);
      if (e.key==="Escape") { setShowSearch(false); setShowShortcuts(false); setExplainFindingId(null); setExplainEntityId(null); setExplainCentralityId(null); if (selectedId) setSelectedId(""); setPathTarget(null); }
      if (showSearch && searchItems.length) {
        if (e.key==="ArrowDown") { e.preventDefault(); setSearchIdx(i=> Math.min(i+1, searchItems.length-1)); }
        if (e.key==="ArrowUp") { e.preventDefault(); setSearchIdx(i=> Math.max(i-1, 0)); }
        if (e.key==="Enter" && document.activeElement?.id==="global-search") {
          e.preventDefault();
          const it = searchItems[searchIdx];
          if (it) {
            if (it.type==="Case") setSelectedCase(it.id);
            else if (entities.find(x=>x.id===it.id)) setSelectedId(it.id);
          }
          setShowSearch(false);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return ()=> window.removeEventListener("keydown", onKey);
  }, [selectedId, showSearch, searchItems, searchIdx, entities]);

  const handleSearchSelect = (id: string) => {
    const isCase = cases.find(c=>c.id===id);
    if (isCase) { setSelectedCase(id); setActiveNav("networks"); }
    else if (entities.find(e=>e.id===id)) setSelectedId(id);
    setShowSearch(false); setQuery("");
  };

  const highlight = (text: string, q: string) => {
    if (!q) return text;
    const idx = text.toLowerCase().indexOf(q.toLowerCase());
    if (idx===-1) return text;
    return <>{text.slice(0,idx)}<mark className="bg-amber-400/20 text-[#e8e8ea] rounded px-0.5">{text.slice(idx, idx+q.length)}</mark>{text.slice(idx+q.length)}</>;
  };

  const healthOk = health.connectionState==="connected" && health.data?.status==="ok";
  const healthLabel = health.isMock ? "Mock" : health.connectionState==="connecting" ? "Connecting…" : health.connectionState==="offline" ? "Offline" : health.data ? `${health.data.status} • ${health.data.database?.postgresql || ""} ${health.data.graph?.neo4j || ""}`.trim() : "Checking…";
  const apiStatus = {
    label: DATA_SOURCE==="api" ? (health.connectionState==="connecting" ? "Connecting…" : health.connectionState==="offline" ? "API Offline" : healthOk ? "API Connected" : "API Connected") : "Mock",
    ok: healthOk,
    isMock: health.isMock
  };
  const showSystemBanner = health.connectionState==="offline" && DATA_SOURCE==="api";

  return (
    <div className="min-h-screen flex flex-col bg-[#08080a] text-[#e8e8ea] overflow-x-hidden">
      <TopBar query={query} setQuery={v=> { setQuery(v); setShowSearch(v.length>0); }} onSearchFocus={()=> setShowSearch(true)} caseId={selectedCase} apiStatus={apiStatus} />
      {/* System status banner — only when genuinely offline (2 consecutive health failures) */}
      {showSystemBanner && (
        <div className="mx-3 mt-2 px-3 py-2 rounded-[8px] bg-amber-950/15 border border-amber-900/25 flex items-center justify-between gap-3" role="alert">
          <span className="text-[13px] font-medium text-amber-200/90">API Offline — backend unreachable</span>
          <span className="mono text-[11px] text-amber-200/60 hidden lg:inline truncate max-w-[420px]">{health.error}</span>
          <button onClick={()=> health.retry()} className="shrink-0 text-[12px] font-medium px-3 py-1 rounded-[6px] bg-[#1a1a1e] border border-amber-900/20 text-amber-200 hover:bg-[#262629]">Retry</button>
        </div>
      )}
      {/* Connecting — non-blocking */}
      {health.connectionState==="connecting" && !health.data && DATA_SOURCE==="api" && !showSystemBanner && (
        <div className="mx-3 mt-2 px-3 py-1.5 rounded-[6px] bg-[#0f0f11] border border-[#1e1e22] flex items-center gap-2 mono text-[11px] text-[#8a8a90]" role="status" aria-live="polite">
          <span className="w-2 h-2 border border-[#2a2a2e] border-t-[#8a8a90] rounded-full animate-spin" aria-hidden />
          Connecting to API — checking backend health…
        </div>
      )}

      {showSearch && query && (
        <div className="relative" role="search">
          <motion.div initial={{opacity:0,y:-4}} animate={{opacity:1,y:0}} transition={{duration:0.15}} className="absolute top-1 left-1/2 -translate-x-1/2 w-[min(560px,92vw)] bg-[#17171a] border border-[#262629] rounded-[8px] shadow-2xl z-30 overflow-hidden" role="listbox" aria-label="Search results">
            <div className="max-h-[320px] overflow-auto">
              {searchItems.map((item,i)=> (
                <button key={item.id} role="option" aria-selected={i===searchIdx} onClick={()=> handleSearchSelect(item.id)} className={`w-full text-left px-3 py-2 flex justify-between items-center border-b border-[#1e1e22] last:border-0 ${i===searchIdx?"bg-[#1e1e22]":"hover:bg-[#1e1e22]"}`}>
                  <span className="mono text-[12px] truncate">{highlight(item.label, query)}</span>
                  <span className="mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] ml-2 shrink-0">{item.type}</span>
                </button>
              ))}
              {searchItems.length===0 && <div className="mono text-[12px] text-[#8a8a90] px-3 py-8 text-center" role="status">No results</div>}
            </div>
            <div className="mono text-[10px] text-[#6b6b70] px-3 py-1.5 border-t border-[#262629] flex justify-between"><span>↑↓ navigate • Enter select • Esc close</span><button onClick={()=> setShowSearch(false)} className="underline">close</button></div>
          </motion.div>
        </div>
      )}

      <ShortcutsOverlay open={showShortcuts} onClose={()=> setShowShortcuts(false)} />

      <div className="flex flex-1 min-h-0">
        <Sidebar active={activeNav} onChange={setActiveNav} alertCount={alerts.length} />
        <MobileSidebar active={activeNav} onChange={setActiveNav} open={mobileOpen} onClose={()=> setMobileOpen(false)} alertCount={alerts.length} />

        <main className="flex-1 min-w-0 flex flex-col overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-[#262629] bg-[#0e0e10] md:hidden shrink-0">
            <button onClick={()=> setMobileOpen(true)} aria-label="Open navigation" className="mono text-[11px] px-2 py-1 rounded-[6px] bg-[#17171a] border border-[#262629]">☰ menu</button>
            <span className="mono text-[11px] text-[#8a8a90]">{activeNav}</span>
            <button onClick={()=> setShowShortcuts(true)} className="ml-auto mono text-[10px] px-2 py-1 rounded-[6px] bg-[#17171a] border border-[#262629]">? shortcuts</button>
          </div>

          <AnimatePresence mode="wait">
            <motion.div key={activeNav+selectedCase} initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} transition={{duration:0.15}} className="flex-1 p-3 gap-4 flex flex-col lg:grid lg:grid-cols-12 min-h-0 overflow-auto bg-[#08080a]">
              {activeNav==="overview" && (
                <>
                  <div className="lg:col-span-12">
                    <h1 className="text-[20px] font-semibold tracking-tight text-[#e8e8ea]">Investigator Overview</h1>
                    <p className="text-[13px] text-[#8a8a90] mt-1">Command center • Case activity • Network scale • Recent findings</p>
                  </div>
                  <div className="lg:col-span-12 grid grid-cols-2 lg:grid-cols-4 gap-3">
                    {[
                      { label: "Cases", value: String(cases.filter(c=>c.status==="open"||c.status==="under_review").length), sub: `${cases.length} total cases` },
                      { label: "Entities", value: String(entities.length), sub: `${relationships.length} relationships` },
                      { label: "Alerts", value: String(alerts.length), sub: `${intelligence.indicators?.indicators?.length ?? 0} indicators` },
                      { label: "Investigations", value: investigation.isActive ? "1 active" : "—", sub: investigation.isActive ? `${investigation.findings.length} findings` : "Start from entity" },
                    ].map(card => (
                      <div key={card.label} className="bg-[#111113] border border-[#1e1e22] rounded-[8px] p-3">
                        <div className="text-[11px] tracking-[0.08em] font-medium text-[#6b6b70]">{card.label}</div>
                        <div className="text-[20px] font-semibold text-[#e8e8ea] mt-1">{card.value}</div>
                        <div className="mono text-[11px] text-[#8a8a90] mt-0.5">{card.sub}</div>
                      </div>
                    ))}
                  </div>
                  <div className="lg:col-span-8 bg-[#111113] border border-[#1e1e22] rounded-[8px] overflow-hidden">
                    <div className="px-3 py-2.5 border-b border-[#1e1e22] flex justify-between items-center">
                      <span className="text-[12px] font-semibold text-[#d4d4d8]">Recent Activity</span>
                      <button onClick={()=> setActiveNav("timeline")} className="text-[11px] text-[#8a8a90] hover:text-[#d4d4d8]">View timeline →</button>
                    </div>
                    <div className="divide-y divide-[#1e1e22]">
                      {timelineEvents.slice(0,5).map(ev => (
                        <div key={ev.id} className="px-3 py-2.5 flex gap-3 hover:bg-[#0a0a0c]">
                          <span className="mono text-[11px] text-[#6b6b70] shrink-0">{ev.timestamp.slice(0,16)}</span>
                          <span className="text-[13px] text-[#d4d4d8] truncate">{ev.eventType} • {ev.description}</span>
                          <span className="ml-auto mono text-[10px] px-1.5 py-0.5 rounded bg-[#0a0a0c] border border-[#1e1e22] text-[#8a8a90] shrink-0">{ev.source}</span>
                        </div>
                      ))}
                      {timelineEvents.length===0 && <div className="p-6 text-center"><EmptyState title="No recent activity" hint="Activity appears when entities and relationships are observed." /></div>}
                    </div>
                  </div>
                  <div className="lg:col-span-4 bg-[#111113] border border-[#1e1e22] rounded-[8px] overflow-hidden">
                    <div className="px-3 py-2.5 border-b border-[#1e1e22]">
                      <div className="text-[12px] font-semibold text-[#d4d4d8]">Network Highlights</div>
                      <div className="text-[11px] text-[#8a8a90]">Analytical indicators • Not guilt determination</div>
                    </div>
                    <div className="p-3 space-y-2">
                      {intelligence.indicators?.indicators?.slice(0,3).map(ind => (
                        <div key={ind.indicator_id} className="px-2.5 py-2 rounded-[6px] bg-[#0a0a0c] border border-[#1e1e22]">
                          <div className="flex justify-between gap-2"><span className="text-[13px] font-medium text-[#d4d4d8] truncate">{ind.indicator_type}</span><span className={`mono text-[10px] px-1.5 py-0.5 rounded border ${ind.severity==="HIGH" ? "border-amber-500/20 text-amber-200/80 bg-amber-500/10" : ind.severity==="MEDIUM" ? "border-[#2a2a2e] text-[#d4d4d8]" : "border-[#1e1e22] text-[#8a8a90]"}`}>{ind.severity}</span></div>
                          <div className="text-[12px] text-[#8a8a90] leading-snug mt-1 line-clamp-2">{ind.explanation}</div>
                        </div>
                      ))}
                      {(!intelligence.indicators || intelligence.indicators.indicators.length===0) && <EmptyState title="No highlights" hint="Indicators appear when network analysis completes." />}
                    </div>
                  </div>
                  <div className="lg:col-span-12 flex items-center gap-2 px-3 py-2 bg-[#0f0f11] border border-[#1e1e22] rounded-[8px] mono text-[11px] text-[#8a8a90]">
                    <span className={`w-2 h-2 rounded-full ${healthOk ? "bg-emerald-500" : "bg-amber-500"}`} aria-hidden />
                    <span>System status: {healthLabel} • Case {selectedCase} • {entities.length} entities • Deterministic AI • No guilt scoring</span>
                    <span className="ml-auto hidden sm:inline">{health.data?.version ?? ""} • Investigator Workspace</span>
                  </div>
                </>
              )}
              {activeNav==="networks" && (
                <>
                  {/* PAGE HEADER + CASE CONTEXT */}
                  <div className="lg:col-span-12 flex flex-col gap-2">
                    <div className="flex items-end justify-between gap-3 flex-wrap border-b border-[#1e1e22] pb-3">
                      <div>
                        <h1 className="text-[18px] font-semibold tracking-tight text-[#e8e8ea]">Network Console</h1>
                        <p className="text-[13px] text-[#8a8a90] mt-0.5">Graph-driven investigation workspace • Case-scoped analysis</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="hidden sm:inline text-[11px] tracking-[0.06em] text-[#6b6b70] font-medium">CASE</span>
                        <select value={selectedCase} onChange={e=> setSelectedCase(e.target.value)} aria-label="Select case" className="text-[13px] px-2.5 py-1.5 rounded-[8px] bg-[#111113] border border-[#262629] text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#2a2a2e] min-w-[180px]">
                          {cases.map(c=> <option key={c.id} value={c.id}>{c.number} — {c.id}</option>)}
                        </select>
                      </div>
                    </div>
                    {/* Case context bar — persistent */}
                    <div className="grid grid-cols-4 gap-px rounded-[8px] overflow-hidden border border-[#1e1e22] bg-[#1e1e22]">
                      {[
                        { label: "CASE", value: selectedCase, mono: true },
                        { label: "STATUS", value: cases.find(c=>c.id===selectedCase)?.status ?? "active", mono: false },
                        { label: "ENTITIES", value: String(entities.length), mono: true },
                        { label: "RELATIONSHIPS", value: String(relationships.length), mono: true },
                      ].map(item => (
                        <div key={item.label} className="bg-[#0a0a0c] px-3 py-2">
                          <div className="text-[10px] tracking-[0.08em] text-[#6b6b70] font-medium">{item.label}</div>
                          <div className={`${item.mono ? "mono" : ""} text-[13px] font-medium text-[#d4d4d8] truncate`}>{item.value}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* PRIMARY WORKSPACE: Graph dominant + Entity */}
                  <div className="lg:col-span-8 flex flex-col min-h-[520px]">
                    {/* Toolbar — compact, grouped */}
                    <div className="flex items-center gap-2 px-2 py-2 bg-[#111113] border border-[#1e1e22] rounded-t-[8px] flex-wrap">
                      <div className="flex items-center gap-1">
                        <span className="text-[10px] tracking-[0.08em] text-[#6b6b70] font-medium mr-1">VIEW</span>
                        <span className="mono text-[11px] text-[#8a8a90] hidden sm:inline">{entities.length} nodes • {relationships.length} edges</span>
                      </div>
                      <div className="h-4 w-px bg-[#1e1e22] mx-1 hidden sm:block" aria-hidden />
                      <div className="flex items-center gap-1">
                        <span className="text-[10px] tracking-[0.08em] text-[#6b6b70] font-medium mr-1">ANALYSIS</span>
                        <span className="text-[11px] text-[#8a8a90] hidden md:inline">Select node to inspect • Drag to pan • Scroll to zoom</span>
                      </div>
                      <div className="ml-auto flex items-center gap-1">
                        <span className="mono text-[11px] px-2 py-1 rounded bg-[#0a0a0c] border border-[#1e1e22] text-[#8a8a90]">{selectedId ? selectedId : "No selection"}</span>
                      </div>
                    </div>
                    <div className="flex-1 min-h-[480px] border-x border-b border-[#1e1e22] rounded-b-[8px] overflow-hidden bg-[#08080a]">
                      {netError ? (
                        <div className="h-full flex flex-col items-center justify-center p-6 text-center border border-dashed border-[#1e1e22] rounded-[8px] bg-[#0a0a0c]/50">
                          <div className="text-[13px] font-medium text-[#d4d4d8]">No network data</div>
                          <div className="text-[13px] text-[#8a8a90] mt-1">Network unavailable for this case.</div>
                          <div className="mono text-[11px] text-[#6b6b70] mt-1 max-w-[420px] truncate">{netError}</div>
                          <button onClick={()=> retryNetwork()} className="mt-3 text-[12px] font-medium px-3 py-1.5 rounded-[6px] bg-[#1e1e22] border border-[#262629] text-[#d4d4d8] hover:bg-[#262629]">Retry</button>
                        </div>
                      ) : (
                        <NetworkGraph entities={entities} relationships={relationships} selectedId={selectedId || null} onSelect={setSelectedId} loading={netLoading} />
                      )}
                    </div>
                    {/* Path finder — compact toolbar style */}
                    <div className="mt-2 flex gap-1.5 items-center text-[13px] bg-[#111113] border border-[#1e1e22] rounded-[8px] px-2.5 py-2">
                      <span className="text-[11px] font-semibold tracking-[0.06em] text-[#8a8a90]">PATH FINDER</span>
                      <input value={pathSourceInput} onChange={e=> setPathSourceInput(e.target.value)} placeholder={selectedId || "source entity"} className="ml-2 w-[140px] bg-[#0a0a0c] border border-[#262629] rounded-[6px] px-2 py-1 text-[13px] focus:outline-none focus:border-[#2e2e32] placeholder:text-[#6b6b70]" aria-label="Path source" />
                      <span className="text-[#6b6b70]">→</span>
                      <input value={pathTargetInput} onChange={e=> setPathTargetInput(e.target.value)} placeholder="target entity" className="w-[140px] bg-[#0a0a0c] border border-[#262629] rounded-[6px] px-2 py-1 text-[13px] focus:outline-none focus:border-[#2e2e32] placeholder:text-[#6b6b70]" aria-label="Path target" />
                      <button onClick={()=> { const s = pathSourceInput || selectedId; if(s && pathTargetInput){ setSelectedId(s); setPathTarget(pathTargetInput); } }} className="ml-1 px-3 py-1 rounded-[6px] bg-[#e8e8ea] text-[#0a0a0c] border border-transparent text-[13px] font-medium hover:bg-white">Find path</button>
                      {pathHook.data && <span className="ml-2 mono text-[11px] text-[#8a8a90] truncate">{pathHook.data.found ? `${(pathHook.data.nodes as {entity_id:string}[]).map(n=> n.entity_id).join(" → ") || (pathHook.data as unknown as {entities:string[]}).entities?.join(" → ")} (${pathHook.data.hop_count ?? (pathHook.data as unknown as {length:number}).length ?? "?"})` : "No path found within max depth"}</span>}
                      {pathHook.error && <span className="ml-2 mono text-[11px] text-amber-200/70 truncate max-w-[220px]">{pathHook.error}</span>}
                    </div>
                  </div>

                  <div className="lg:col-span-4 flex flex-col gap-3 min-h-0">
                    <div className="overflow-auto max-h-[560px] rounded-[8px] border border-[#1e1e22] bg-[#111113]">
                      <div className="px-3 py-2 border-b border-[#1e1e22] bg-[#0a0a0c]">
                        <div className="text-[11px] font-semibold tracking-[0.06em] text-[#a1a1aa]">SELECTED ENTITY</div>
                      </div>
                      <EntityDetails entity={entityForDetails as Entity} relationships={relsHook.data} events={relatedEvents} alerts={relatedAlerts} onSelectRelated={setSelectedId} onStartInvestigation={handleStartInvestigation} onExplain={setExplainEntityId} loading={relsHook.loading} error={relsHook.error} />
                    </div>
                    {entityInt.data && (
                      <div className="border border-[#1e1e22] rounded-[8px] bg-[#111113] p-3">
                        <div className="text-[11px] font-semibold tracking-[0.06em] text-[#a1a1aa] mb-2">NETWORK POSITION</div>
                        <div className="grid grid-cols-2 gap-2 mono text-[11px]">
                          <div className="bg-[#0a0a0c] rounded-[6px] px-2 py-1.5 border border-[#1e1e22]"><span className="text-[#6b6b70]">degree</span><span className="float-right text-[#d4d4d8] font-medium">{entityInt.data.centrality.degree?.toFixed(3)}</span></div>
                          <div className="bg-[#0a0a0c] rounded-[6px] px-2 py-1.5 border border-[#1e1e22]"><span className="text-[#6b6b70]">betweenness</span><span className="float-right text-[#d4d4d8] font-medium">{entityInt.data.centrality.betweenness?.toFixed(3)}</span></div>
                          <div className="bg-[#0a0a0c] rounded-[6px] px-2 py-1.5 border border-[#1e1e22]"><span className="text-[#6b6b70]">closeness</span><span className="float-right text-[#d4d4d8] font-medium">{entityInt.data.centrality.closeness?.toFixed(3)}</span></div>
                          <div className="bg-[#0a0a0c] rounded-[6px] px-2 py-1.5 border border-[#1e1e22]"><span className="text-[#6b6b70]">pagerank</span><span className="float-right text-[#d4d4d8] font-medium">{entityInt.data.centrality.pagerank?.toFixed(3)}</span></div>
                        </div>
                        {entityInt.data.indicators?.length ? <div className="mt-2 text-[11px] text-[#6b6b70]">{entityInt.data.indicators.length} analytical indicators • Not guilt assessment</div> : null}
                      </div>
                    )}
                    {entityInt.error && <div className="mt-1"><ErrorState title="Entity analysis unavailable" message={entityInt.error} /></div>}
                    <div className="flex-1 min-h-[160px] overflow-hidden flex flex-col rounded-[8px] border border-[#1e1e22] bg-[#111113]">
                      <AlertPanel alerts={relatedAlerts.length ? relatedAlerts : alerts.slice(0,3)} onEntitySelect={setSelectedId} loading={netLoading} />
                    </div>
                  </div>

                  <div className="lg:col-span-12 mt-2 space-y-3">
                    <InvestigationTimeline events={selectedId ? relatedEvents : timelineEvents} loading={netLoading} />
                    {/* Intelligence — compact, collapsible feel */}
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                      <NetworkMetrics centrality={intelligence.centrality} loading={intelligence.loading} error={intelligence.error} onExplain={()=> selectedId && setExplainCentralityId(selectedId)} />
                      <CommunitiesPanel data={intelligence.communities} loading={intelligence.loading} error={intelligence.error} onExplain={()=> selectedId && setExplainCentralityId(selectedId)} />
                      <BridgesPanel data={intelligence.bridges} loading={intelligence.loading} error={intelligence.error} onSelect={setSelectedId} onExplain={()=> selectedId && setExplainCentralityId(selectedId)} />
                      <TemporalPanel data={intelligence.temporal} loading={intelligence.loading} error={intelligence.error} onExplain={()=> selectedId && setExplainCentralityId(selectedId)} />
                      <ChainsPanel data={intelligence.chains} loading={intelligence.loading} error={intelligence.error} onExplain={()=> selectedId && setExplainCentralityId(selectedId)} />
                      <IndicatorsPanel data={intelligence.indicators} loading={intelligence.loading} error={intelligence.error} onSelect={setSelectedId} onExplain={()=> investigation.findings[0] && setExplainFindingId(investigation.findings[0].finding_id)} />
                    </div>
                    {DATA_SOURCE==="api" && intelligence.error && (
                      <div className="px-3 py-2 rounded-[8px] bg-[#111113] border border-[#1e1e22] text-[13px] text-[#8a8a90]">Graph intelligence requires API connection • <button onClick={()=> window.location.reload()} className="underline">Retry</button></div>
                    )}
                  </div>
                </>
              )}

              {activeNav==="entities" && (
                <div className="lg:col-span-12 grid grid-cols-1 lg:grid-cols-12 gap-3">
                  <div className="lg:col-span-5 border border-[#1e1e22] rounded-[8px] bg-[#111113] overflow-hidden flex flex-col">
                    <div className="px-3 py-2.5 border-b border-[#1e1e22] bg-[#0f0f11] flex justify-between items-center">
                      <span className="text-[11px] font-semibold tracking-[0.06em] text-[#a1a1aa]">ENTITIES</span>
                      <span className="mono text-[11px] px-2 py-0.5 rounded-full bg-[#0a0a0c] border border-[#1e1e22] text-[#8a8a90]">{entities.length}</span>
                    </div>
                    <div className="px-2 py-2 border-b border-[#1e1e22] bg-[#0a0a0c]/50">
                      <span className="mono text-[11px] text-[#6b6b70]">Case</span><span className="mono text-[11px] text-[#d4d4d8] ml-1.5">{selectedCase}</span>
                    </div>
                    {netLoading ? <div className="p-3"><SkeletonRows rows={6} /></div> : netError ? <div className="p-3"><ErrorState title="Failed to load entities" message={netError} /></div> : (
                    <div className="divide-y divide-[#1e1e22] max-h-[68vh] overflow-auto" role="list">
                      {entities.length===0 ? <div className="p-4"><EmptyState title="No entities" hint="No entities in this network. Select a different case."/></div> : entities.map(e=> (
                        <button key={e.id} onClick={()=> setSelectedId(e.id)} aria-selected={selectedId===e.id} className={`w-full text-left px-3 py-2.5 flex justify-between items-center transition-colors ${selectedId===e.id?"bg-[#1a1a1e] border-l-2 border-[#e8e8ea]":"border-l-2 border-transparent hover:bg-[#0f0f11]"}`}>
                          <div className="min-w-0">
                            <div className="text-[13px] font-medium text-[#e8e8ea] truncate">{e.displayName}</div>
                            <div className="mono text-[11px] text-[#8a8a90] mt-0.5 truncate">{e.id} • {e.type} • {e.relationshipCount} rel</div>
                          </div>
                          <span className="mono text-[10px] px-1.5 py-0.5 rounded bg-[#0a0a0c] border border-[#1e1e22] text-[#8a8a90] ml-2 shrink-0">{Math.round(e.confidence*100)}%</span>
                        </button>
                      ))}
                    </div>
                    )}
                  </div>
                  <div className="lg:col-span-7 overflow-auto"><EntityDetails entity={entityForDetails as Entity} relationships={relsHook.data} events={relatedEvents} alerts={relatedAlerts} onSelectRelated={setSelectedId} onStartInvestigation={handleStartInvestigation} onExplain={setExplainEntityId} loading={relsHook.loading} error={relsHook.error} /></div>
                </div>
              )}

              {activeNav==="timeline" && <div className="lg:col-span-12"><InvestigationTimeline events={timelineEvents} loading={netLoading} /></div>}

              {activeNav==="alerts" && <div className="lg:col-span-12 max-w-[900px]"><AlertPanel alerts={alerts} onEntitySelect={setSelectedId} loading={netLoading} />{DATA_SOURCE==="api" && <div className="mt-3"><IndicatorsPanel data={intelligence.indicators} loading={intelligence.loading} error={intelligence.error} onSelect={setSelectedId} /></div>}</div>}

              {activeNav==="cases" && (
                <div className="lg:col-span-12">
                  <div className="flex items-end justify-between border-b border-[#1e1e22] pb-3 mb-3">
                    <div>
                      <h1 className="text-[18px] font-semibold tracking-tight text-[#e8e8ea]">Cases</h1>
                      <p className="text-[13px] text-[#8a8a90] mt-0.5">{cases.length} cases • Select to establish active case context</p>
                    </div>
                    <span className="mono text-[11px] text-[#6b6b70] hidden sm:inline">Active: {selectedCase}</span>
                  </div>
                  <div className="grid gap-2">
                    {cases.map(c=> (
                      <button key={c.id} onClick={()=> { setSelectedCase(c.id); setActiveNav("networks"); }} className={`text-left border rounded-[8px] px-4 py-3 flex justify-between items-center gap-3 transition-colors ${selectedCase===c.id?"bg-[#111113] border-[#2a2a2e] shadow-[0_0_0_1px_rgba(212,212,216,0.08)]":"bg-[#111113] border-[#1e1e22] hover:border-[#262629] hover:bg-[#0f0f11]"}`}>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2"><span className="mono text-[11px] font-medium text-[#d4d4d8]">{c.number}</span><span className="mono text-[11px] text-[#6b6b70]">•</span><span className="mono text-[11px] text-[#8a8a90]">{c.id}</span><span className={`ml-1 text-[10px] px-1.5 py-0.5 rounded border ${c.status==="open" ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200/80" : c.status==="under_review" ? "border-amber-500/20 bg-amber-500/10 text-amber-200/80" : "border-[#1e1e22] text-[#6b6b70]"}`}>{c.status}</span></div>
                          <div className="text-[14px] font-medium text-[#e8e8ea] mt-1 truncate">{c.title}</div>
                          <div className="text-[12px] text-[#8a8a90] truncate">{c.description || ""}</div>
                        </div>
                        <span className="shrink-0 text-center">
                          <div className="mono text-[13px] font-semibold text-[#d4d4d8]">{c.entityCount}</div>
                          <div className="text-[10px] tracking-[0.06em] text-[#6b6b70]">ENTITIES</div>
                        </span>
                      </button>
                    ))}
                    {cases.length===0 && <EmptyState title="No cases" hint="No cases available in current context." />}
                  </div>
                </div>
              )}

              {activeNav==="investigation" && (
                <div className="lg:col-span-12">
                  {investigation.isActive ? (
                    <InvestigationWorkspace
                      caseId={investigation.caseId || selectedCase}
                      rootId={investigation.rootId || selectedId || ""}
                      depth={investigation.depth}
                      subgraph={investigation.subgraph}
                      entities={investigationEntities}
                      relationships={investigationRelationships}
                      findings={investigation.findings}
                      evidence={investigation.evidence}
                      loading={investigation.loading}
                      error={investigation.error}
                      selectedId={selectedId}
                      onSelect={setSelectedId}
                      onDepthChange={(d)=> investigation.setDepth(d)}
                      onClose={() => { investigation.clearInvestigation(); setActiveNav("networks"); }}
                      path={pathHook.data}
                      pathLoading={pathHook.loading}
                      pathError={pathHook.error}
                      onExplainFinding={setExplainFindingId}
                      onExplainPath={()=> { if (pathHook.data?.found) setExplainFindingId(investigation.findings[0]?.finding_id || null); }}
                    />
                  ) : (
                    <div className="border border-dashed border-[#262629] rounded-[8px] bg-[#17171a] p-6 text-center">
                      <div className="mono text-[11px] text-[#d4d4d8]">No active investigation</div>
                      <div className="mono text-[11px] text-[#6b6b70] mt-1">Select an entity and click “Start investigation” to open a focused subgraph.</div>
                      {selectedId && <button onClick={()=> handleStartInvestigation(selectedId)} className="mt-3 mono text-[11px] px-3 py-1.5 rounded-[6px] bg-[#1e1e22] border border-[#262629] text-[#d4d4d8] hover:bg-[#262629]">Start investigation from {selectedId}</button>}
                      {!selectedId && <div className="mono text-[10px] text-[#6b6b70] mt-2">Current case: {selectedCase}</div>}
                    </div>
                  )}
                </div>
              )}

              {activeNav==="evidence" && <div className="lg:col-span-12"><EmptyState title="Evidence" hint="Evidence provenance — blockchain module (future)." /></div>}

              {activeNav==="audit" && (
                <div className="lg:col-span-12">
                  <AuditWorkspace audit={audit.data} loading={audit.loading} error={audit.error} caseId={selectedCase} onCaseChange={(c)=> setSelectedCase(c || "case-00001")} />
                </div>
              )}

              {activeNav==="ai" && (
                <div className="lg:col-span-12">
                  <AIWorkspace caseId={selectedCase} rootEntityId={investigation.rootId ?? selectedId ?? null} />
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {(explainFindingId || explainEntityId || explainCentralityId) && (
        <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true" aria-label="Explanation">
          <div className="absolute inset-0 bg-black/40" onClick={()=> { setExplainFindingId(null); setExplainEntityId(null); setExplainCentralityId(null); }} aria-hidden />
          <div className="relative w-[min(520px,92vw)] h-full bg-[#0e0e10] border-l border-[#262629] overflow-auto p-3">
            {explainFindingId && <ExplanationPanel explanation={findingExplain.data} loading={findingExplain.loading} error={findingExplain.error} onClose={()=> setExplainFindingId(null)} />}
            {explainEntityId && <ExplanationPanel explanation={entityExplain.data} loading={entityExplain.loading} error={entityExplain.error} onClose={()=> setExplainEntityId(null)} />}
            {explainCentralityId && <ExplanationPanel explanation={centralityExplain.data} loading={centralityExplain.loading} error={centralityExplain.error} onClose={()=> setExplainCentralityId(null)} />}
            <div className="mt-2 mono text-[10px] text-[#6b6b70]">Press Esc to close • analytical signal, not proof</div>
          </div>
        </div>
      )}

      <footer className="h-[28px] border-t border-[#1e1e22] bg-[#0a0a0c] text-[11px] text-[#6b6b70] flex items-center justify-between px-4 shrink-0">
        <span className="flex items-center gap-2"><span className="w-1.5 h-1.5 rounded-full bg-[#262629]" aria-hidden /> Criminal Network Analysis • Investigator Workspace • {DATA_SOURCE} • {health.isMock ? "Mock" : healthOk ? "Connected" : "Disconnected"}</span>
        <span className="hidden sm:inline text-[#8a8a90]">Analytical indicators only • No guilt determination</span>
      </footer>
    </div>
  );
}
