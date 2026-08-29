import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useInvestigationData } from "../../hooks/useInvestigationData";

function highlight(text: string, q: string) {
  if (!q) return text;
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx === -1) return text;
  return <>{text.slice(0, idx)}<mark className="bg-amber-400/20 text-[#e8e8ea] px-0.5 rounded">{text.slice(idx, idx+q.length)}</mark>{text.slice(idx+q.length)}</>;
}

export function GlobalSearch({ query, setQuery, onSelect, onClose }: { query: string; setQuery: (v: string) => void; onSelect: (id: string) => void; onClose: () => void }) {
  const { allSearchItems } = useInvestigationData();
  const [idx, setIdx] = useState(0);
  const ref = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    if (!query.trim()) return allSearchItems.slice(0, 8);
    const q = query.toLowerCase();
    return allSearchItems.filter(i => i.id.toLowerCase().includes(q) || i.label.toLowerCase().includes(q)).slice(0, 10);
  }, [query, allSearchItems]);

  useEffect(()=> setIdx(0), [filtered]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") { e.preventDefault(); setIdx(i=> Math.min(i+1, filtered.length-1)); }
      if (e.key === "ArrowUp") { e.preventDefault(); setIdx(i=> Math.max(i-1, 0)); }
      if (e.key === "Enter" && filtered[idx]) { onSelect(filtered[idx].id); }
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [filtered, idx, onSelect, onClose]);

  return (
    <AnimatePresence>
      <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.18 }} className="absolute top-[38px] left-0 right-0 mx-auto max-w-[560px] bg-[#17171a] border border-[#262629] rounded-[8px] shadow-xl overflow-hidden z-20" role="listbox" aria-label="Search results">
        <div className="max-h-[320px] overflow-auto">
          {filtered.map((item, i) => (
            <button key={item.id} role="option" aria-selected={i===idx} onClick={() => onSelect(item.id)} className={`w-full text-left px-3 py-2 flex items-center justify-between border-b border-[#1e1e22] last:border-0 focus:outline-none ${i===idx ? "bg-[#1e1e22]" : "hover:bg-[#1e1e22]"}`}>
              <span className="mono text-[12px] text-[#e8e8ea]">{highlight(item.label, query)}</span>
              <span className="mono text-[10px] px-1.5 py-0.5 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90]">{item.type}</span>
            </button>
          ))}
          {filtered.length === 0 && <div className="mono text-[12px] text-[#8a8a90] px-3 py-6 text-center" role="status">No results</div>}
        </div>
        <div className="mono text-[10px] text-[#6b6b70] px-3 py-1.5 border-t border-[#262629]">↑↓ navigate • Enter select • Esc close • / focus</div>
      </motion.div>
    </AnimatePresence>
  );
}
