"use client";
import { useCallback, useSyncExternalStore } from "react";

const KEY = "bi-sql-solved";
const listeners = new Set<() => void>();

function read(): string {
  try {
    return localStorage.getItem(KEY) ?? "[]";
  } catch {
    return "[]";
  }
}
// In-memory fallback so progress still shows this session if storage is blocked.
let memory: string | null = null;
const snapshot = () => memory ?? read();
const subscribe = (cb: () => void) => {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
};

/** Which SQL exercises the learner has solved (stored in this browser only). */
export function useSolved() {
  const raw = useSyncExternalStore(subscribe, snapshot, () => "[]");
  let ids: string[] = [];
  try {
    ids = JSON.parse(raw) as string[];
  } catch {
    /* corrupt value: treat as empty */
  }
  const markSolved = useCallback((id: string) => {
    let cur: string[] = [];
    try { cur = JSON.parse(snapshot()) as string[]; } catch { /* ignore */ }
    if (cur.includes(id)) return;
    const next = JSON.stringify([...cur, id]);
    memory = next;
    try { localStorage.setItem(KEY, next); } catch { /* storage blocked: memory fallback */ }
    listeners.forEach((l) => l());
  }, []);
  return { solved: new Set(ids), markSolved };
}
