import React from "react";
import { motion } from "framer-motion";

const items = [
  { id: "overview", label: "Overview", icon: "◫" },
  { id: "cases", label: "Cases", icon: "▭" },
  { id: "entities", label: "Entities", icon: "◯" },
  { id: "networks", label: "Networks", icon: "⬡" },
  { id: "investigation", label: "Investigation", icon: "⬢" },
  { id: "timeline", label: "Timeline", icon: "◷" },
  { id: "evidence", label: "Evidence", icon: "▤" },
  { id: "alerts", label: "Alerts", icon: "⚑", badge: 4 },
  { id: "audit", label: "Audit", icon: "⎙" },
];

export function Sidebar({ active, onChange, collapsed }: { active: string; onChange: (id: string) => void; collapsed?: boolean }) {
  return (
    <nav className={`${collapsed ? "w-[56px]" : "w-[180px]"} shrink-0 bg-[#0e0e10] border-r border-[#262629] py-2 flex flex-col gap-1 hidden md:flex`}>
      {items.map(item => {
        const isActive = active === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onChange(item.id)}
            className={`mx-1.5 h-[32px] flex items-center gap-2.5 px-2.5 mono text-[11px] tracking-wide rounded-[8px] border transition-colors ${isActive ? "bg-[#1a1a1e] border-[#2e2e32] text-[#e8e8ea]" : "border-transparent text-[#8a8a90] hover:bg-[#17171a] hover:text-[#d4d4d8]"}`}
          >
            <span className="text-[12px] w-4 text-center">{item.icon}</span>
            {!collapsed && <span>{item.label}</span>}
            {!collapsed && item.badge && (
              <span className="ml-auto bg-[#1e1e22] border border-[#262629] text-[#a1a1aa] text-[10px] px-1 py-0 rounded-[6px]">{item.badge}</span>
            )}
            {isActive && !collapsed && <motion.span layoutId="active-dot" className="ml-auto w-1 h-1 rounded-full bg-[#d4d4d8]" />}
          </button>
        );
      })}
      <div className="mt-auto mx-2 p-2 rounded-[8px] bg-[#17171a] border border-[#262629]">
        <div className="mono text-[10px] text-[#8a8a90]">CLASSIFICATION</div>
        <div className="mono text-[11px] text-[#a1a1aa]">SYNTHETIC_DEMO</div>
        <div className="mono text-[10px] text-[#6b6b70] mt-1">No guilt assessment</div>
      </div>
    </nav>
  );
}

export function MobileSidebar({ active, onChange, open, onClose }: { active: string; onChange: (id: string) => void; open: boolean; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 md:hidden">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="absolute left-0 top-0 bottom-0 w-[220px] bg-[#0e0e10] border-r border-[#262629] p-2">
        {items.map(item => (
          <button key={item.id} onClick={() => { onChange(item.id); onClose(); }} className={`w-full h-9 flex items-center gap-2 px-3 mono text-[12px] rounded-[8px] ${active===item.id ? "bg-[#1a1a1e] text-white" : "text-[#8a8a90]"}`}>
            <span>{item.icon}</span>{item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
