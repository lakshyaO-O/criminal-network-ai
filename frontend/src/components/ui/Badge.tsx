import React from "react";

export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "muted" | "accent" }) {
  const map = {
    neutral: "bg-[#1e1e22] border-[#262629] text-[#a1a1aa]",
    muted: "bg-[#151519] border-[#262629] text-[#8a8a90]",
    accent: "bg-[#1a1a1e] border-[#2e2e32] text-[#d4d4d8]"
  };
  return <span className={`inline-flex items-center px-1.5 py-0.5 mono text-[10px] tracking-wide border rounded-[6px] ${map[tone]}`}>{children}</span>;
}
