import React from "react";
export function EmptyState({ title, hint, icon = "—", action }: { title: string; hint?: string; icon?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-7 text-center border border-dashed border-[#1e1e22] rounded-[8px] bg-[#0f0f11]">
      <div className="w-8 h-8 rounded-[8px] bg-[#111113] border border-[#1e1e22] flex items-center justify-center text-[13px] text-[#6b6b70] mb-2.5" aria-hidden>{icon}</div>
      <div className="text-[13px] font-medium text-[#d4d4d8]">{title}</div>
      {hint && <div className="text-[13px] text-[#8a8a90] mt-1 max-w-[32ch] leading-snug">{hint}</div>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
