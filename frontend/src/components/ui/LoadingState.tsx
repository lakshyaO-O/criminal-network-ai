import React from "react";
export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-2 mono text-[11px] text-[#8a8a90] px-3 py-4">
      <span className="w-3 h-3 border border-[#2e2e32] border-t-[#6b6b70] rounded-full animate-spin" aria-hidden />
      {label}…
    </div>
  );
}
export function InlineLoading({ label }: { label: string }) {
  return (
    <div className="w-full h-full flex items-center justify-center bg-[#0e0e10] border border-[#262629] rounded-[8px] mono text-[11px] text-[#8a8a90]" role="status">
      <span className="w-3 h-3 border border-[#2e2e32] border-t-[#6b6b70] rounded-full animate-spin mr-2" />{label}
    </div>
  );
}
