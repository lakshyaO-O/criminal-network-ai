import React, { useEffect, useRef, useState, useMemo } from "react";
import cytoscape from "cytoscape";
import { Entity, Relationship, EntityType } from "../../types";
import { EmptyState } from "../ui/EmptyState";
import { LoadingState } from "../ui/LoadingState";

type Props = { entities: Entity[]; relationships: Relationship[]; selectedId: string | null; onSelect: (id: string) => void; loading?: boolean };

const typeColor: Record<string, string> = {
  Person: "#d4d4d8",
  Organization: "#a1a1aa",
  Phone: "#9aa0a6",
  Vehicle: "#8a8a90",
  Location: "#c4b5a0",
  Account: "#a8b5c0"
};

const allTypes: EntityType[] = ["Person", "Organization", "Phone", "Vehicle", "Location", "Account"];

export function NetworkGraph({ entities, relationships, selectedId, onSelect, loading }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [filterTypes, setFilterTypes] = useState<Set<EntityType>>(new Set(allTypes));

  const visibleEntities = useMemo(() => entities.filter(e => filterTypes.has(e.type)), [entities, filterTypes]);
  const visibleRels = useMemo(() => relationships.filter(r => {
    const s = entities.find(e => e.id === r.source)?.type;
    const t = entities.find(e => e.id === r.target)?.type;
    return (!s || filterTypes.has(s)) && (!t || filterTypes.has(t));
  }), [relationships, entities, filterTypes]);

  useEffect(() => {
    if (!containerRef.current) return;
    const elements: cytoscape.ElementDefinition[] = [
      ...visibleEntities.map(e => ({ data: { id: e.id, label: e.displayName, type: e.type } })),
      ...visibleRels.map(r => ({ data: { id: r.id, source: r.source, target: r.target, label: r.type } }))
    ];
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        { selector: "node", style: { "background-color": (ele: any) => typeColor[ele.data("type")] || "#888", "label": "data(label)", "color": "#e8e8ea", "font-size": "8px", "font-family": "JetBrains Mono, monospace", "text-valign": "bottom", "text-halign": "center", "text-margin-y": 8, "width": "22px" as any, "height": "22px" as any, "border-width": 1, "border-color": "#262629", "text-wrap": "ellipsis", "text-max-width": "70px" as any } },
        { selector: "node[type='Person']", style: { "shape": "ellipse", "width": "26px" as any, "height": "26px" as any } },
        { selector: "node[type='Organization']", style: { "shape": "round-rectangle", "width": "28px" as any, "height": "22px" as any } },
        { selector: "node[type='Location']", style: { "shape": "diamond", "width": "24px" as any, "height": "24px" as any } },
        { selector: "edge", style: { "width": 1, "line-color": "#2a2a2e", "target-arrow-color": "#2a2a2e", "target-arrow-shape": "triangle", "arrow-scale": 0.7, "curve-style": "bezier", "label": "data(label)", "font-size": "6px", "color": "#6b6b70", "font-family": "JetBrains Mono, monospace", "text-rotation": "autorotate", "text-background-color": "#0e0e10", "text-background-opacity": 0.8, "text-background-padding": "1px" } },
        { selector: "node:selected", style: { "border-width": 2, "border-color": "#e8e8ea", "background-color": "#fff" } },
        { selector: ".selected", style: { "border-width": 2, "border-color": "#e8e8ea", "background-color": "#fff" } },
        { selector: ".hover", style: { "background-color": "#fff", "border-color": "#e8e8ea" } },
        { selector: ".neighbor", style: { "border-color": "#3a3a3e" } },
        { selector: ".highlight-edge", style: { "line-color": "#c4c4c8", "target-arrow-color": "#c4c4c8", "width": 1.8 } },
        { selector: ".selected-edge", style: { "line-color": "#e8e8ea", "target-arrow-color": "#e8e8ea", "width": 2 } },
        { selector: ".dim", style: { "opacity": 0.18 } }
      ],
      layout: { name: "cose", animate: false, nodeRepulsion: () => 4800, idealEdgeLength: () => 90, gravity: 0.25 } as any,
      minZoom: 0.3, maxZoom: 2.5, wheelSensitivity: 0.2
    });
    cy.on("tap", "node", evt => onSelect(evt.target.id()));
    cy.on("tap", evt => { if (evt.target === cy) onSelect(evt.target.id()); });
    cy.on("mouseover", "node", evt => setHoverId(evt.target.id()));
    cy.on("mouseout", "node", () => setHoverId(null));
    cyRef.current = cy;
    return () => { cy.destroy(); cyRef.current = null; };
  }, [visibleEntities, visibleRels, onSelect]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("dim neighbor highlight-edge hover selected selected-edge");
    if (selectedId) {
      const sel = cy.getElementById(selectedId);
      if (sel.nonempty()) {
        sel.addClass("selected");
        const nb = sel.closedNeighborhood();
        cy.elements().not(nb).addClass("dim");
        nb.filter("edge").addClass("highlight-edge");
        nb.filter("node").addClass("neighbor");
        sel.removeClass("dim").addClass("selected");
        sel.connectedEdges().addClass("selected-edge");
      }
    }
    if (hoverId && hoverId !== selectedId) {
      const h = cy.getElementById(hoverId);
      if (h.nonempty()) {
        const nb = h.closedNeighborhood();
        nb.addClass("neighbor");
        nb.filter("edge").addClass("highlight-edge");
      }
    }
  }, [selectedId, hoverId]);

  const fit = () => cyRef.current?.fit(undefined, 30);
  const clear = () => onSelect("");
  const zoomIn = () => cyRef.current && cyRef.current.zoom({ level: cyRef.current.zoom() * 1.25, renderedPosition: { x: cyRef.current.width() / 2, y: cyRef.current.height() / 2 } } as any);
  const zoomOut = () => cyRef.current && cyRef.current.zoom({ level: cyRef.current.zoom() * 0.8, renderedPosition: { x: cyRef.current.width() / 2, y: cyRef.current.height() / 2 } } as any);

  if (loading) return (
    <div className="h-[420px] border border-[#1e1e22] rounded-[8px] bg-[#0a0a0c] flex flex-col">
      <div className="flex items-center gap-2 px-3 py-3 border-b border-[#1e1e22]">
        <span className="w-3 h-3 border border-[#2a2a2e] border-t-[#6b6b70] rounded-full animate-spin" aria-hidden />
        <span className="text-[13px] text-[#8a8a90]">Loading network — preparing graph</span>
      </div>
      <div className="flex-1 p-3 space-y-2 animate-pulse">
        <div className="h-3 bg-[#111113] rounded w-3/4" />
        <div className="h-3 bg-[#111113] rounded w-1/2" />
        <div className="h-32 bg-[#111113] rounded mt-4" />
      </div>
    </div>
  );
  if (visibleEntities.length === 0) return (
    <div className="h-[420px] border border-[#1e1e22] rounded-[8px] bg-[#0a0a0c] flex flex-col items-center justify-center p-6 text-center">
      <div className="w-10 h-10 rounded-[8px] bg-[#111113] border border-[#1e1e22] flex items-center justify-center text-[16px] mb-3">⬡</div>
      <div className="text-[13px] font-medium text-[#d4d4d8]">No entities match filter</div>
      <div className="text-[13px] text-[#8a8a90] mt-1 max-w-[32ch]">Adjust node-type filters above or select a different case. The graph is case-scoped.</div>
      <button onClick={() => setFilterTypes(new Set(allTypes))} className="mt-3 text-[12px] px-3 py-1.5 rounded-[6px] bg-[#17171a] border border-[#262629] text-[#d4d4d8] hover:bg-[#1e1e22]">Reset filters</button>
    </div>
  );

  return (
    <div className="relative w-full h-full bg-[#08080a] border border-[#1e1e22] overflow-hidden flex flex-col">
      {/* Filter toolbar — compact */}
      <div className="flex items-center gap-1 px-3 py-2 border-b border-[#1e1e22] bg-[#0f0f11] flex-wrap" role="toolbar" aria-label="Graph filters">
        <span className="text-[10px] font-semibold tracking-[0.08em] text-[#6b6b70] mr-2">FILTER</span>
        {allTypes.map(t => {
          const active = filterTypes.has(t);
          return (
            <button key={t} aria-pressed={active} aria-label={`Filter ${t}`} onClick={() => setFilterTypes(prev => { const n = new Set(prev); if (n.has(t)) n.delete(t); else n.add(t); if (n.size===0) allTypes.forEach(x=>n.add(x)); return n; })} className={`text-[12px] px-2 py-1 rounded-[6px] border flex items-center gap-1.5 transition-colors ${active ? "bg-[#1a1a1e] border-[#262629] text-[#e8e8ea]" : "border-transparent text-[#6b6b70] hover:text-[#a1a1aa] hover:bg-[#111113]"}`}>
              <span className="w-2 h-2 rounded-full border border-black/20" style={{ background: typeColor[t] }} aria-hidden />{t}
            </button>
          );
        })}
        <div className="ml-auto flex items-center gap-2 mono text-[11px] text-[#6b6b70]">
          <span className="hidden sm:inline">{visibleEntities.length} nodes • {visibleRels.length} edges</span>
          {selectedId && <span className="px-2 py-0.5 rounded-full bg-[#e8e8ea] text-[#0a0a0c] font-medium">{selectedId}</span>}
        </div>
      </div>
      <div className="relative flex-1 min-h-[380px] bg-[#08080a]">
        <div ref={containerRef} className="w-full h-full" role="application" aria-label="Network graph. Use Tab to reach controls, click nodes to select." tabIndex={0} onKeyDown={e => { if (e.key === "Escape") clear(); if (e.key === "+" || e.key === "=") zoomIn(); if (e.key === "-") zoomOut(); if (e.key === "0") fit(); }} />
        {/* Zoom controls */}
        <div className="absolute top-3 right-3 flex flex-col gap-1">
          <button aria-label="Zoom in" onClick={zoomIn} className="w-7 h-7 rounded-[6px] bg-[#111113] border border-[#1e1e22] text-[12px] hover:bg-[#17171a] hover:border-[#262629] focus:outline-none focus:ring-1 focus:ring-[#2a2a2e]">+</button>
          <button aria-label="Zoom out" onClick={zoomOut} className="w-7 h-7 rounded-[6px] bg-[#111113] border border-[#1e1e22] text-[12px] hover:bg-[#17171a] hover:border-[#262629] focus:outline-none focus:ring-1 focus:ring-[#2a2a2e]">−</button>
          <button aria-label="Fit graph" onClick={fit} className="w-7 h-7 rounded-[6px] bg-[#111113] border border-[#1e1e22] text-[9px] font-medium hover:bg-[#17171a] focus:outline-none focus:ring-1 focus:ring-[#2a2a2e]">FIT</button>
          <button aria-label="Clear selection" onClick={clear} className="w-7 h-7 rounded-[6px] bg-[#111113] border border-[#1e1e22] text-[9px] font-medium hover:bg-[#17171a] focus:outline-none focus:ring-1 focus:ring-[#2a2a2e]">CLR</button>
        </div>
        {/* Legend */}
        <div className="absolute bottom-2 left-2 flex items-center gap-2 px-2 py-1 rounded-full bg-[#111113]/90 border border-[#1e1e22] backdrop-blur">
          {allTypes.slice(0,4).map(t => (
            <span key={t} className="flex items-center gap-1 mono text-[10px] text-[#8a8a90]"><span className="w-2 h-2 rounded-full" style={{ background: typeColor[t] }} />{t}</span>
          ))}
          <span className="w-px h-3 bg-[#1e1e22] mx-1" aria-hidden />
          <span className="mono text-[10px] text-[#6b6b70] hidden sm:inline">selected: white ring • hover: highlight neighbors</span>
        </div>
        <div className="absolute bottom-2 right-2 mono text-[10px] text-[#6b6b70] hidden lg:block bg-[#111113]/80 px-1.5 py-0.5 rounded border border-[#1e1e22]">drag • scroll • click • Esc</div>
      </div>
    </div>
  );
}
