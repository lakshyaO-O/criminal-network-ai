import React from "react";
import { motion, AnimatePresence } from "framer-motion";
export function ShortcutsOverlay({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/50 z-40" onClick={onClose} aria-hidden />
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }} transition={{ duration: 0.15 }} role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(420px,92vw)] bg-[#17171a] border border-[#262629] rounded-[8px] shadow-2xl z-50 overflow-hidden">
            <div className="px-4 py-3 border-b border-[#262629] flex justify-between items-center">
              <span className="mono text-[11px] font-semibold text-[#d4d4d8]">KEYBOARD SHORTCUTS</span>
              <button onClick={onClose} aria-label="Close shortcuts" className="mono text-[10px] px-2 py-1 rounded-[6px] bg-[#0e0e10] border border-[#262629] text-[#8a8a90] hover:text-[#d4d4d8] focus:outline-none focus:ring-1 focus:ring-[#3a3a3e]">Esc</button>
            </div>
            <div className="px-4 py-3 mono text-[11px] space-y-2">
              <div className="flex justify-between"><span className="text-[#8a8a90]">Focus search</span><span className="px-1.5 py-0.5 rounded border border-[#262629] bg-[#0e0e10] text-[#d4d4d8]">/</span></div>
              <div className="flex justify-between"><span className="text-[#8a8a90]">Close panel / clear selection</span><span className="px-1.5 py-0.5 rounded border border-[#262629] bg-[#0e0e10] text-[#d4d4d8]">Esc</span></div>
              <div className="flex justify-between"><span className="text-[#8a8a90]">Show this help</span><span className="px-1.5 py-0.5 rounded border border-[#262629] bg-[#0e0e10] text-[#d4d4d8]">?</span></div>
              <div className="flex justify-between"><span className="text-[#8a8a90]">Navigate search results</span><span className="px-1.5 py-0.5 rounded border border-[#262629] bg-[#0e0e10] text-[#d4d4d8]">↑ ↓ Enter</span></div>
              <div className="flex justify-between"><span className="text-[#8a8a90]">Graph: zoom / fit / clear</span><span className="px-1.5 py-0.5 rounded border border-[#262629] bg-[#0e0e10] text-[#d4d4d8]">+ − 0 Esc</span></div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
