const TTL_MS = 45_000;

type Entry = { at: number; data: unknown };

const cache = new Map<string, Entry>();
const inflight = new Map<string, Promise<unknown>>();

function cacheKey(path: string, method: string) {
  return `${method.toUpperCase()} ${path}`;
}

function cacheableGet(path: string, method: string) {
  if (method !== "GET") return false;
  if (/\/jobs\/\d+(?:\?|$)/.test(path)) return false;
  return true;
}

function shouldInvalidate(path: string, method: string) {
  if (method === "GET" || method === "HEAD") return false;
  if (/\/codebase\/branches(?:\?|$)/.test(path)) return false;
  return true;
}

export function clearHttpCache() {
  cache.clear();
  inflight.clear();
}

export function peekGet<T>(path: string): T | undefined {
  const hit = cache.get(cacheKey(path, "GET"));
  return hit ? (hit.data as T) : undefined;
}

export async function httpJson<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const key = cacheKey(path, method);
  if (cacheableGet(path, method)) {
    const hit = cache.get(key);
    if (hit && Date.now() - hit.at < TTL_MS) return hit.data as T;
    const pending = inflight.get(key);
    if (pending) return pending as Promise<T>;
    if (hit) {
      if (!inflight.has(key)) {
        const refresh = loadJson<T>(path, init, method)
          .catch(() => hit.data as T)
          .finally(() => inflight.delete(key));
        inflight.set(key, refresh);
      }
      return hit.data as T;
    }
  }
  const run = loadJson<T>(path, init, method);
  if (cacheableGet(path, method)) {
    const tracked = run.finally(() => inflight.delete(key));
    inflight.set(key, tracked);
    return tracked;
  }
  return run;
}

async function loadJson<T>(path: string, init: RequestInit | undefined, method: string): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    let detail = text || response.statusText;
    try {
      const parsed = JSON.parse(text);
      if (parsed?.detail) detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
    } catch {
      if (/internal server error/i.test(text) || response.status >= 500) {
        detail = "This request could not be completed. Please retry.";
      }
    }
    throw new Error(detail);
  }
  const data = (await response.json()) as T;
  if (shouldInvalidate(path, method)) clearHttpCache();
  else if (cacheableGet(path, method)) cache.set(cacheKey(path, "GET"), { at: Date.now(), data });
  return data;
}
