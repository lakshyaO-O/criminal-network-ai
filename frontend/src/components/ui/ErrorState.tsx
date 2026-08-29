import React from "react";
export function ErrorState({ title = "Request failed", message, onRetry }: { title?: string; message?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="border border-amber-900/30 bg-amber-950/20 rounded-[8px] px-3 py-3 mono">
      <div className="text-[11px] text-amber-200/90 font-medium">{title}</div>
      {message && <div className="text-[11px] text-amber-200/60 mt-1">{message}</div>}
      {onRetry && <button onClick={onRetry} className="mt-2 mono text-[11px] px-2 py-1 rounded-[6px] bg-[#1e1e22] border border-[#262629] text-[#d4d4d8] hover:bg-[#262629]">Retry</button>}
    </div>
  );
}
export function ConnectionStatus({ online = true }: { online?: boolean }) {
  return (
    <span aria-label={online ? "Connection available" : "Connection unavailable"} className={`inline-flex items-center gap-1.5 mono text-[11px] px-2 h-[24px] rounded-[6px] border ${online ? "bg-[#17171a] border-[#262629] text-[#a1a1aa]" : "bg-amber-950/20 border-amber-900/30 text-amber-200/80"}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${online ? "bg-emerald-500/80" : "bg-amber-500"}`} aria-hidden />
      {online ? "system operational" : "connection unavailable (mock mode)"}
    </span>
  );
}
