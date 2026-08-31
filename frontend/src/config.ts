const envSource =
  (typeof process !== "undefined" ? (process.env as Record<string, string | undefined>).REACT_APP_DATA_SOURCE : undefined) ||
  (typeof import.meta !== "undefined" ? (import.meta as unknown as { env?: Record<string, string> }).env?.REACT_APP_DATA_SOURCE : undefined) ||
  (typeof import.meta !== "undefined" ? (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_DATA_SOURCE : undefined);
export const DATA_SOURCE: "mock" | "api" = (envSource as "mock" | "api") || "api";

function resolveApiUrl(): string {
  const raw =
    (typeof process !== "undefined" ? (process.env as Record<string, string | undefined>).REACT_APP_API_URL : undefined) ||
    (typeof import.meta !== "undefined" ? (import.meta as unknown as { env?: Record<string, string> }).env?.REACT_APP_API_URL : undefined) ||
    (typeof import.meta !== "undefined" ? (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL : undefined) ||
    "";
  const trimmed = raw.trim().replace(/\/$/, "");
  if (trimmed) return trimmed;
  // In production (Vercel) without env, use relative URL so Vercel rewrites can proxy /api
  // — avoids hard-coded http://localhost:8000 which is unreachable from the browser.
  if (typeof window !== "undefined") {
    const h = window.location.hostname;
    if (h && h !== "localhost" && h !== "127.0.0.1") {
      return ""; // relative — combined as `/api/...` and handled by vercel.json rewrites
    }
  }
  return "http://localhost:8000";
}

export const API_URL: string = resolveApiUrl();
export const API_PREFIX = "/api";
