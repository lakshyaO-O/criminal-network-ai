const envSource = (typeof process !== "undefined" ? (process.env as Record<string, string | undefined>).REACT_APP_DATA_SOURCE : undefined) || (typeof import.meta !== "undefined" ? (import.meta as unknown as { env?: Record<string, string> }).env?.REACT_APP_DATA_SOURCE : undefined);
export const DATA_SOURCE: "mock" | "api" = (envSource as "mock" | "api") || "api";
export const API_URL: string =
  (typeof process !== "undefined" ? (process.env as Record<string, string | undefined>).REACT_APP_API_URL : undefined) ||
  "http://localhost:8000";
export const API_PREFIX = "/api";
