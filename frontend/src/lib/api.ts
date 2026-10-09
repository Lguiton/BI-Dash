import type { FilterState } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8020";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public details: string[] = [],
  ) {
    super(message);
  }
}

export function filterQuery(f: FilterState, extra: Record<string, string | number> = {}): string {
  const p = new URLSearchParams();
  (Object.keys(f) as (keyof FilterState)[]).forEach((k) => {
    if (f[k]) p.set(k, f[k]);
  });
  Object.entries(extra).forEach(([k, v]) => p.set(k, String(v)));
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function toError(res: Response): Promise<ApiError> {
  let message = `Request failed (${res.status})`;
  let details: string[] = [];
  try {
    const body = await res.json();
    const d = body?.detail;
    if (typeof d === "string") message = d;
    else if (Array.isArray(d)) message = d.map((x) => x?.msg ?? String(x)).join("; ");
    else if (d && typeof d === "object") {
      message = d.message ?? message;
      details = Array.isArray(d.errors) ? d.errors : [];
    }
  } catch {
    /* non-JSON error body: keep the generic message */
  }
  return new ApiError(message, res.status, details);
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(`Can't reach the analytics API at ${API_BASE}. Is the backend running?`, 0);
  }
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}

export async function postFile<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "POST", body });
  } catch {
    throw new ApiError(`Can't reach the analytics API at ${API_BASE}. Is the backend running?`, 0);
  }
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}

export async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(`Can't reach the analytics API at ${API_BASE}. Is the backend running?`, 0);
  }
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}

export async function deleteJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  } catch {
    throw new ApiError(`Can't reach the analytics API at ${API_BASE}. Is the backend running?`, 0);
  }
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}

export async function putJson<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch {
    throw new ApiError(`Can't reach the analytics API at ${API_BASE}. Is the backend running?`, 0);
  }
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}

export async function postForm<T>(path: string, body: FormData): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "POST", body });
  } catch {
    throw new ApiError(`Can't reach the analytics API at ${API_BASE}. Is the backend running?`, 0);
  }
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}

export async function patchJson<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch {
    throw new ApiError(`Can't reach the analytics API at ${API_BASE}. Is the backend running?`, 0);
  }
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}
