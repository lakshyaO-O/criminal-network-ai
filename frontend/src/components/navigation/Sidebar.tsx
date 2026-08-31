import React from "react";
import { motion } from "framer-motion";

const groups = [
  {
    label: "WORKSPACE",
    items: [
      { id: "overview", label: "Overview", icon: "◫" },
      { id: "cases", label: "Cases", icon: "▭" },
      { id: "networks", label: "Network", icon: "⬡" },
    ],
  },
  {
    label: "INVESTIGATION",
    items: [
      { id: "entities", label: "Entities", icon: "◯" },
      { id: "investigation", label: "Investigation", icon: "⬢" },
      { id: "timeline", label: "Timeline", icon: "◷" },
      { id: "evidence", label: "Evidence", icon: "▤" },
      { id: "alerts", label: "Alerts", icon: "⚑" },
    ],
  },
  {
    label: "INTELLIGENCE",
    items: [
      { id: "ai", label: "AI Assist", icon: "✦" },
      { id: "audit", label: "Audit", icon: "⎙" },
    ],
  },
];

const allItems = groups.flatMap(g => g.items);

export function Sidebar({ active, onChange, collapsed, alertCount }: { active: string; onChange: (id: string) => void; collapsed?: boolean; alertCount?: number }) {
  return (
    <nav className={`${collapsed ? "w-[56px]" : "w-[200px]"} shrink-0 bg-[#0a0a0c] border-r border-[#1e1e22] flex flex-col hidden md:flex overflow-hidden`}>
      <div className="flex-1 py-3 overflow-auto">
        {groups.map(group => (
          <div key={group.label} className="mb-4">
            {!collapsed && (
              <div className="px-3 mb-1.5 text-[10px] font-semibold tracking-[0.12em] text-[#6b6b70]">{group.label}</div>
            )}
            <div className="flex flex-col gap-0.5">
              {group.items.map(item => {
                const isActive = active === item.id;
                const badge = item.id === "alerts" && alertCount !== undefined ? alertCount : (item as unknown as { badge?: number }).badge;
                return (
                  <button
                    key={item.id}
                    onClick={() => onChange(item.id)}
                    className={`mx-2 h-[30px] flex items-center gap-2.5 px-2.5 text-[13px] rounded-[6px] transition-colors relative ${isActive ? "bg-[#17171a] text-[#e8e8ea] font-medium" : "text-[#8a8a90] hover:bg-[#111113] hover:text-[#d4d4d8] font-normal"}`}
                  >
                    {isActive && <span className="absolute left-0 top-1 bottom-1 w-[2px] bg-[#d4d4d8] rounded-full" aria-hidden />}
                    <span className="text-[11px] w-4 text-center opacity-80">{item.icon}</span>
                    {!collapsed && <span>{item.label}</span>}
                    {!collapsed && badge !== undefined && badge > 0 && (
                      <span className="ml-auto bg-[#1e1e22] border border-[#262629] text-[#a1a1aa] text-[10px] px-1.5 py-0 rounded-full min-w-[18px] text-center">{badge}</span>
                    )}
                    {isActive && !collapsed && <motion.span layoutId="active-dot" className="ml-auto w-1 h-1 rounded-full bg-[#d4d4d8]" />}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="shrink-0 mx-3 mb-3 p-2.5 rounded-[8px] bg-[#111113] border border-[#1e1e22]">
        <div className="text-[10px] font-semibold tracking-[0.1em] text-[#6b6b70]">CLASSIFICATION</div>
        <div className="text-[11px] font-medium text-[#a1a1aa] mt-0.5">SYNTHETIC DATASET</div>
        <div className="text-[10px] text-[#6b6b70] mt-1 leading-snug">Analytical use only • No guilt determination</div>
      </div>
    </nav>
  );
}

export function MobileSidebar({ active, onChange, open, onClose, alertCount }: { active: string; onChange: (id: string) => void; open: boolean; onClose: () => void; alertCount?: number }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 md:hidden">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="absolute left-0 top-0 bottom-0 w-[240px] bg-[#0a0a0c] border-r border-[#1e1e22] p-3 overflow-auto">
        {groups.map(group => (
          <div key={group.label} className="mb-4">
            <div className="text-[10px] font-semibold tracking-[0.12em] text-[#6b6b70] mb-1.5 px-2">{group.label}</div>
            {group.items.map(item => {
              const badge = item.id === "alerts" && alertCount !== undefined ? alertCount : (item as unknown as { badge?: number }).badge;
              return (
              <button key={item.id} onClick={() => { onChange(item.id); onClose(); }} className={`w-full h-9 flex items-center gap-2.5 px-3 text-[13px] rounded-[6px] ${active===item.id ? "bg-[#17171a] text-white font-medium" : "text-[#8a8a90] hover:bg-[#111113]"}`}>
                <span className="text-[11px] w-4 text-center">{item.icon}</span>{item.label}
                {badge !== undefined && badge > 0 && <span className="ml-auto bg-[#1e1e22] border border-[#262629] text-[#a1a1aa] text-[10px] px-1.5 py-0 rounded-full">{badge}</span>}
              </button>
            )})}
          </div>
        ))}
      </div>
    </div>
  );
}
