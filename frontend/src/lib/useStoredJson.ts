"use client";
import { useCallback, useMemo, useSyncExternalStore } from "react";

// Per-browser storage for small learner state (saved queries, quiz scores).
// Falls back to memory when storage is blocked, so the page still works for the session.
const listeners = new Map<string, Set<() => void>>();
const memory = new Map<string, string>();

function readRaw(key: string): string | null {
  if (memory.has(key)) return memory.get(key)!;
  try { return localStorage.getItem(key); } catch { return null; }
}

export function useStoredJson<T>(key: string, initial: T): [T, (next: T) => void] {
  const subscribe = useCallback((cb: () => void) => {
    let set = listeners.get(key);
    if (!set) { set = new Set(); listeners.set(key, set); }
    set.add(cb);
    window.addEventListener("storage", cb);
    return () => { set!.delete(cb); window.removeEventListener("storage", cb); };
  }, [key]);
  const raw = useSyncExternalStore(subscribe, () => readRaw(key), () => null);
  const value = useMemo<T>(() => {
    if (raw === null) return initial;
    try { return JSON.parse(raw) as T; } catch { return initial; }
    // `initial` is a constant default supplied by the caller
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [raw]);
  const set = useCallback((next: T) => {
    const s = JSON.stringify(next);
    memory.set(key, s);
    try { localStorage.setItem(key, s); } catch { /* storage blocked: memory fallback */ }
    listeners.get(key)?.forEach((l) => l());
  }, [key]);
  return [value, set];
}
