import { API_URL, API_PREFIX } from "../config";

type FetchOpts = RequestInit & { timeoutMs?: number };

export class ApiError extends Error {
  status: number;
  url: string;
  constructor(message: string, status: number, url: string) {
    super(message);
    this.status = status;
    this.url = url;
  }
}

async function fetchJson<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const url = `${API_URL}${API_PREFIX}${path}`;
  const controller = new AbortController();
  const signal = opts.signal ? ((): AbortSignal => {
    const s = opts.signal as AbortSignal;
    s.addEventListener("abort", () => controller.abort());
    if (s.aborted) controller.abort();
    return controller.signal;
  })() : controller.signal;
  const timeout = setTimeout(() => controller.abort(), opts.timeoutMs ?? 8000);
  try {
    const res = await fetch(url, { ...opts, signal, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      let msg = text;
      try { const j = JSON.parse(text); msg = j.detail || j.message || text; } catch { /* raw */ }
      throw new ApiError(msg || `Request failed ${res.status}`, res.status, url);
    }
    return (await res.json()) as T;
  } catch (e: unknown) {
    if (e instanceof ApiError) throw e;
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new ApiError(`Request timed out or cancelled — ${url}`, 0, url);
    }
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.includes("Failed to fetch") || msg.includes("NetworkError") || msg.includes("abort") || msg.includes("timed out")) {
      throw new ApiError(`Connection unavailable — backend not reachable at ${url}`, 0, url);
    }
    throw new ApiError(msg, 0, url);
  } finally {
    clearTimeout(timeout);
  }
}

export const apiClient = {
  get: <T>(path: string, opts?: FetchOpts) => fetchJson<T>(path, { ...opts, method: "GET" }),
  post: <T>(path: string, body: unknown, opts?: FetchOpts) => fetchJson<T>(path, { ...opts, method: "POST", body: JSON.stringify(body) }),
};
