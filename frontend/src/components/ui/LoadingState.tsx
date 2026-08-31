import React from "react";
export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-2.5 px-3 py-3">
      <span className="w-3.5 h-3.5 border-[2px] border-[#1e1e22] border-t-[#6b6b70] rounded-full animate-spin" aria-hidden />
      <span className="text-[13px] text-[#8a8a90]">{label}…</span>
      <span className="ml-auto mono text-[11px] text-[#6b6b70]">Please wait</span>
    </div>
  );
}
export function InlineLoading({ label }: { label: string }) {
  return (
    <div className="w-full h-full flex items-center justify-center bg-[#0a0a0c] border border-[#1e1e22] rounded-[8px] text-[13px] text-[#8a8a90]" role="status">
      <span className="w-3.5 h-3.5 border-[2px] border-[#1e1e22] border-t-[#6b6b70] rounded-full animate-spin mr-2" />{label}
    </div>
  );
}
export function SkeletonRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="p-3 space-y-2" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-3 bg-[#111113] rounded animate-pulse" style={{ width: `${70 + (i % 3) * 10}%` }} />
      ))}
    </div>
  );
}
