import React from "react";
export function ErrorState({ title = "Request failed", message, onRetry }: { title?: string; message?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="border border-amber-900/25 bg-amber-950/15 rounded-[8px] px-3 py-2.5">
      <div className="text-[13px] font-medium text-amber-200/90">{title}</div>
      {message && <div className="mono text-[11px] text-amber-200/60 mt-1 truncate" title={message}>{message}</div>}
      {onRetry && <button onClick={onRetry} className="mt-2 text-[12px] px-2.5 py-1 rounded-[6px] bg-[#1a1a1e] border border-amber-900/20 text-amber-200 hover:bg-[#262629]">Retry</button>}
    </div>
  );
}
export function InlineError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-[#0a0a0c] border border-[#1e1e22] rounded-[6px]">
      <span className="mono text-[11px] text-amber-200/70 truncate flex-1">API connection required — {message}</span>
      {onRetry && <button onClick={onRetry} className="shrink-0 text-[11px] px-2 py-1 rounded bg-[#17171a] border border-[#262629] text-[#d4d4d8]">Retry</button>}
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
