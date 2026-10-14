"use client";
import { useStoredJson } from "./useStoredJson";

export type Mode = "work" | "learn";

/** Work mode is the default. It hides every learning page; nothing is deleted. */
export function useMode(): [Mode, (m: Mode) => void] {
  const [raw, set] = useStoredJson<string>("bi-mode", "work");
  return [raw === "learn" ? "learn" : "work", (m) => set(m)];
}

/** Fields the person sells. Empty means show every field. */
export function useMyFields(): [string[], (ids: string[]) => void] {
  return useStoredJson<string[]>("bi-myfields", []);
}

// Pages that exist for study and practice. Work mode shows a switch prompt instead of these.
const LEARN_EXACT = ["/tracks", "/quiz", "/glossary", "/review", "/lab", "/analysis", "/studio", "/nlp-dl", "/design", "/diagrams", "/compare",
  "/python", "/ml", "/mlhand", "/ai", "/apache", "/pipeline", "/scd", "/schema", "/toolmap", "/portfolio"];

export function isLearnPath(path: string): boolean {
  const p = path.length > 1 ? path.replace(/\/+$/, "") : path;
  return LEARN_EXACT.includes(p);
}

/** Tabs for a field page. Study-only tabs (simulators, cheat sheets, exam prep) are hidden in Work mode (`always` hides them in both modes); `current` falls back to the first tab left. */
export function useWorkTabs<T extends { id: string }>(all: T[], studyOnly: string[], wanted: string, always = false): { tabs: T[]; current: string } {
  const [mode] = useMode();
  const tabs = always || mode === "work" ? all.filter((t) => !studyOnly.includes(t.id)) : all;
  return { tabs, current: tabs.some((t) => t.id === wanted) ? wanted : tabs[0].id };
}
