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
import { useFindingExplanation, useEntityExplanation, usePathExplanation, useCentralityExplanation } from "./hooks/useExplainability";
import { useAuditTrail } from "./hooks/useAudit";

export default function App() {
  const health = useHealth(30000);
  const [selectedCase, setSelectedCase] = useState<string>("case-00001");
  const { entities, relationships, timelineEvents, alerts, cases, allSearchItems, loading: netLoading, error: netError } = useNetworkData(selectedCase);
  const investigation = useInvestigationWorkspace();
  const intelligence = useGraphIntelligence(selectedCase);
  const [selectedId, setSelectedId] = useState<string>("person-00001");
  // Explainability state
  const [explainFindingId, setExplainFindingId] = useState<string | null>(null);
  const [explainEntityId, setExplainEntityId] = useState<string | null>(null);
  const [explainCentrality, setExplainCentrality] = useState(false);
  const findingExplain = useFindingExplanation(explainFindingId, selectedCase, investigation.rootId);
  const entityExplain = useEntityExplanation(explainEntityId);
  const centralityExplain = useCentralityExplanation(explainCentrality);
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

  // Clear stale investigation when case changes
  useEffect(() => {
    if (investigation.isActive && investigation.caseId !== selectedCase) investigation.clearInvestigation();
  }, [selectedCase, investigation.isActive, investigation.caseId]);

  // Search: real API-backed via entities/cases/relationships, debounced display already; no extra fetch needed because network provides canonical list
  const searchItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allSearchItems.slice(0,8);
    return allSearchItems.filter(i=> i.id.toLowerCase().includes(q) || i.label.toLowerCase().includes(q)).slice(0,10);
  }, [query, allSearchItems]);

  useEffect(()=> { if (!selectedCase) setExplainFindingId(null); }, [selectedCase, explainFindingId]);

  useEffect(()=> { if (selectedId && explainEntityId && explainEntityId !== selectedId) setExplainEntityId(null); }, [selectedId, explainEntityId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (document.activeElement as HTMLElement)?.tagName;
      const isInput = tag==="INPUT" || tag==="TEXTAREA";
      if (e.key==="/" && !isInput) { e.preventDefault(); document.getElementById("global-search")?.focus(); setShowSearch(true); }
      if (e.key==="?" && !isInput) setShowShortcuts(v=>!v);
      if (e.key==="Escape") { setShowSearch(false); setShowShortcuts(false); setExplainFindingId(null); setExplainEntityId(null); setExplainCentrality(false); if (selectedId) setSelectedId(""); setPathTarget(null); }
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

  const healthLabel = health.isMock ? "mock mode" : health.error ? "connection unavailable" : health.data ? `${health.data.status} • ${health.data.database?.postgresql || ""} ${health.data.graph?.neo4j || ""}`.trim() : "checking…";
  const healthOk = !health.error && health.data?.status==="ok";

  return (
    <div className="min-h-screen flex flex-col bg-[#0e0e10] text-[#e8e8ea] overflow-x-hidden">
      <TopBar query={query} setQuery={v=> { setQuery(v); setShowSearch(v.length>0); }} onSearchFocus={()=> setShowSearch(true)} />
      {/* health bar */}
      <div className="h-6 flex items-center justify-between px-3 mono text-[10px] border-b border-[#262629] bg-[#0e0e10]" role="status" aria-live="polite">
        <span className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${healthOk ? "bg-emerald-500/80" : health.isMock ? "bg-sky-500/80" : "bg-amber-500"}`} aria-hidden />
          <span className={health.error ? "text-amber-200/80" : "text-[#8a8a90]"}>{DATA_SOURCE==="api" ? (health.error ? `API: ${health.error}` : `API: ${healthLabel}`) : "DATA_SOURCE=mock • deterministic"}</span>
          {DATA_SOURCE==="api" && health.data && <span className="hidden sm:inline text-[#6b6b70] ml-2">v{health.data.version} • {health.data.service}</span>}
        </span>
        <span className="hidden sm:inline text-[#6b6b70]">case {selectedCase} • {entities.length} entities • {relationships.length} relationships</span>
      </div>

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
        <Sidebar active={activeNav} onChange={setActiveNav} />
        <MobileSidebar active={activeNav} onChange={setActiveNav} open={mobileOpen} onClose={()=> setMobileOpen(false)} />

        <main className="flex-1 min-w-0 flex flex-col overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-[#262629] bg-[#0e0e10] md:hidden shrink-0">
            <button onClick={()=> setMobileOpen(true)} aria-label="Open navigation" className="mono text-[11px] px-2 py-1 rounded-[6px] bg-[#17171a] border border-[#262629]">☰ menu</button>
            <span className="mono text-[11px] text-[#8a8a90]">{activeNav}</span>
            <button onClick={()=> setShowShortcuts(true)} className="ml-auto mono text-[10px] px-2 py-1 rounded-[6px] bg-[#17171a] border border-[#262629]">? shortcuts</button>
          </div>

          <AnimatePresence mode="wait">
            <motion.div key={activeNav+selectedCase} initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}} transition={{duration:0.15}} className="flex-1 p-2 sm:p-3 gap-3 flex flex-col lg:grid lg:grid-cols-12 min-h-0 overflow-auto">
              {(activeNav==="networks" || activeNav==="overview") && (
                <>
                  <div className="lg:col-span-8 flex flex-col min-h-[380px]">
                    <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
                      <div className="mono text-[11px] font-semibold tracking-[0.08em] text-[#d4d4d8]">NETWORK — {selectedCase} <span className="text-[#6b6b70] font-normal">• {DATA_SOURCE}</span></div>
                      <div className="flex items-center gap-1">
                        <select value={selectedCase} onChange={e=> setSelectedCase(e.target.value)} aria-label="Select case" className="mono text-[11px] px-2 py-1 rounded-[6px] bg-[#17171a] border border-[#262629] text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">
                          {cases.map(c=> <option key={c.id} value={c.id}>{c.number} — {c.id}</option>)}
                        </select>
                      </div>
                    </div>
                    {netError ? <ErrorState title="Network unavailable" message={netError} /> : <div className="flex-1 min-h-[420px]"><NetworkGraph entities={entities} relationships={relationships} selectedId={selectedId || null} onSelect={setSelectedId} loading={netLoading} /></div>}
                    {/* Path finder - restrained */}
                    <div className="mt-2 flex gap-1 items-center mono text-[11px] border border-[#262629] rounded-[8px] bg-[#17171a] px-2 py-1.5">
                      <span className="text-[#6b6b70]">PATH</span>
                      <input value={pathSourceInput} onChange={e=> setPathSourceInput(e.target.value)} placeholder={selectedId || "source"} className="ml-2 w-[130px] bg-[#0e0e10] border border-[#262629] rounded px-1.5 py-0.5 mono text-[11px] focus:outline-none focus:border-[#2e2e32]" aria-label="Path source" />
                      <span className="text-[#6b6b70]">→</span>
                      <input value={pathTargetInput} onChange={e=> setPathTargetInput(e.target.value)} placeholder="target" className="w-[130px] bg-[#0e0e10] border border-[#262629] rounded px-1.5 py-0.5 mono text-[11px] focus:outline-none focus:border-[#2e2e32]" aria-label="Path target" />
                      <button onClick={()=> { const s = pathSourceInput || selectedId; if(s && pathTargetInput){ setSelectedId(s); setPathTarget(pathTargetInput); } }} className="ml-1 px-2 py-0.5 rounded-[6px] bg-[#1e1e22] border border-[#262629] hover:bg-[#262629]">find</button>
                      {pathHook.data && <span className="ml-2 text-[#8a8a90]">{pathHook.data.found ? `${(pathHook.data.nodes as {entity_id:string}[]).map(n=> n.entity_id).join(" → ") || (pathHook.data as unknown as {entities:string[]}).entities?.join(" → ")} (${pathHook.data.hop_count ?? (pathHook.data as unknown as {length:number}).length ?? "?"})` : "no path"}</span>}
                      {pathHook.error && <span className="ml-2 text-amber-200/70 truncate max-w-[200px]">{pathHook.error}</span>}
                    </div>
                  </div>

                  <div className="lg:col-span-4 flex flex-col gap-3 min-h-0">
                    <div className="overflow-auto max-h-[520px]">
                      <EntityDetails entity={entityForDetails as Entity} relationships={relsHook.data} events={relatedEvents} alerts={relatedAlerts} onSelectRelated={setSelectedId} onStartInvestigation={handleStartInvestigation} onExplain={setExplainEntityId} loading={relsHook.loading} error={relsHook.error} />
                      {entityInt.data && (
                        <div className="mt-2 border border-[#262629] rounded-[8px] bg-[#17171a] p-2 mono text-[11px]">
                          <div className="text-[11px] font-semibold text-[#d4d4d8] mb-1">CENTRALITY (analysis)</div>
                          <div className="grid grid-cols-2 gap-1 text-[#8a8a90]">
                            <span>degree {entityInt.data.centrality.degree?.toFixed(3)}</span>
                            <span>betweenness {entityInt.data.centrality.betweenness?.toFixed(3)}</span>
                            <span>closeness {entityInt.data.centrality.closeness?.toFixed(3)}</span>
                            <span>pagerank {entityInt.data.centrality.pagerank?.toFixed(3)}</span>
                          </div>
                          {entityInt.data.indicators?.length ? <div className="mt-1 text-[10px] text-[#6b6b70]">{entityInt.data.indicators.length} analytical indicators</div> : null}
                        </div>
                      )}
                      {entityInt.error && <div className="mt-1"><ErrorState title="Entity analysis unavailable" message={entityInt.error} /></div>}
                    </div>
                    <div className="flex-1 min-h-[180px] overflow-hidden flex flex-col">
                      <AlertPanel alerts={relatedAlerts.length ? relatedAlerts : alerts.slice(0,3)} onEntitySelect={setSelectedId} loading={netLoading} />
                    </div>
                  </div>

                  <div className="lg:col-span-12 mt-1 space-y-3">
                    <InvestigationTimeline events={selectedId ? relatedEvents : timelineEvents} loading={netLoading} />
                    {/* Intelligence grid - dense workstation, not dashboard cards */}
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                      <NetworkMetrics centrality={intelligence.centrality} loading={intelligence.loading} error={intelligence.error} onExplain={()=> setExplainCentrality(true)} />
                      <CommunitiesPanel data={intelligence.communities} loading={intelligence.loading} error={intelligence.error} onExplain={()=> investigation.findings[0] && setExplainFindingId(investigation.findings[0].finding_id)} />
                      <BridgesPanel data={intelligence.bridges} loading={intelligence.loading} error={intelligence.error} onSelect={setSelectedId} onExplain={()=> investigation.findings[0] && setExplainFindingId(investigation.findings[0].finding_id)} />
                      <TemporalPanel data={intelligence.temporal} loading={intelligence.loading} error={intelligence.error} onExplain={()=> setExplainCentrality(true)} />
                      <ChainsPanel data={intelligence.chains} loading={intelligence.loading} error={intelligence.error} onExplain={()=> setExplainCentrality(true)} />
                      <IndicatorsPanel data={intelligence.indicators} loading={intelligence.loading} error={intelligence.error} onSelect={setSelectedId} onExplain={()=> investigation.findings[0] && setExplainFindingId(investigation.findings[0].finding_id)} />
                    </div>
                    {DATA_SOURCE==="api" && intelligence.error && <ErrorState title="Graph intelligence unavailable" message={intelligence.error} />}
                  </div>
                </>
              )}

              {activeNav==="entities" && (
                <div className="lg:col-span-12 grid grid-cols-1 lg:grid-cols-12 gap-3">
                  <div className="lg:col-span-5 border border-[#262629] rounded-[8px] bg-[#17171a] overflow-hidden flex flex-col">
                    <div className="px-3 py-2 border-b border-[#262629] mono text-[11px] font-semibold flex justify-between"><span>ENTITIES ({entities.length})</span><span className="text-[#6b6b70] font-normal truncate ml-2">{netError ? "error" : `${selectedCase}`}</span></div>
                    {netLoading ? <div className="p-3 mono text-[11px] text-[#8a8a90]">Loading…</div> : netError ? <div className="p-3"><ErrorState title="Failed to load entities" message={netError} /></div> : (
                    <div className="divide-y divide-[#1e1e22] max-h-[70vh] overflow-auto" role="list">
                      {entities.length===0 ? <div className="p-4"><EmptyState title="No entities" hint="No entities in this network."/></div> : entities.map(e=> (
                        <button key={e.id} onClick={()=> setSelectedId(e.id)} aria-selected={selectedId===e.id} className={`w-full text-left px-3 py-2 flex justify-between items-center hover:bg-[#1e1e22] ${selectedId===e.id?"bg-[#1e1e22] border-l-2 border-[#3a3a3e]":"border-l-2 border-transparent"}`}>
                          <div className="min-w-0"><div className="mono text-[11px] text-[#d4d4d8] truncate">{e.id} — {e.displayName}</div><div className="mono text-[10px] text-[#6b6b70]">{e.type} • {e.relationshipCount} rel</div></div>
                          <span className="mono text-[10px] text-[#8a8a90]">{Math.round(e.confidence*100)}%</span>
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
                <div className="lg:col-span-12 grid gap-2">
                  {cases.map(c=> (
                    <button key={c.id} onClick={()=> { setSelectedCase(c.id); setActiveNav("networks"); }} className={`text-left border rounded-[8px] px-4 py-3 flex justify-between items-center gap-2 hover:border-[#2e2e32] ${selectedCase===c.id?"bg-[#1a1a1e] border-[#2e2e32]":"bg-[#17171a] border-[#262629]"}`}>
                      <div><div className="mono text-[11px] text-[#d4d4d8]">{c.number} — {c.id}</div><div className="text-[13px] text-[#a1a1aa]">{c.title}</div><div className="mono text-[10px] text-[#6b6b70]">{c.description || ""}</div></div>
                      <span className="mono text-[10px] px-2 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] shrink-0">{c.status} • {c.entityCount} entities</span>
                    </button>
                  ))}
                  {cases.length===0 && <EmptyState title="No cases" />}
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
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {(explainFindingId || explainEntityId || explainCentrality) && (
        <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true" aria-label="Explanation">
          <div className="absolute inset-0 bg-black/40" onClick={()=> { setExplainFindingId(null); setExplainEntityId(null); setExplainCentrality(false); }} aria-hidden />
          <div className="relative w-[min(520px,92vw)] h-full bg-[#0e0e10] border-l border-[#262629] overflow-auto p-3">
            {explainFindingId && <ExplanationPanel explanation={findingExplain.data} loading={findingExplain.loading} error={findingExplain.error} onClose={()=> setExplainFindingId(null)} />}
            {explainEntityId && <ExplanationPanel explanation={entityExplain.data} loading={entityExplain.loading} error={entityExplain.error} onClose={()=> setExplainEntityId(null)} />}
            {explainCentrality && <ExplanationPanel explanation={centralityExplain.data} loading={centralityExplain.loading} error={centralityExplain.error} onClose={()=> setExplainCentrality(false)} />}
            <div className="mt-2 mono text-[10px] text-[#6b6b70]">Press Esc to close • analytical signal, not proof</div>
          </div>
        </div>
      )}

      <footer className="h-6 border-t border-[#262629] bg-[#0e0e10] mono text-[10px] text-[#6b6b70] flex items-center justify-between px-3 shrink-0">
        <span>SIH 26189 • {DATA_SOURCE} • neutral terminology • {health.isMock ? "mock" : healthOk ? "connected" : "disconnected"}</span>
        <span className="hidden sm:inline">Not guilt assessment • analytical indicators only</span>
      </footer>
    </div>
  );
}
