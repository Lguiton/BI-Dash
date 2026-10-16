"use client";
import { useSyncExternalStore } from "react";

const Q = "(min-width: 1280px)";
/** True on a wide screen, where the agent can sit beside the tools instead of on its own tab. */
export function useWide(): boolean {
  return useSyncExternalStore(
    (cb) => { const m = window.matchMedia(Q); m.addEventListener("change", cb); return () => m.removeEventListener("change", cb); },
    () => window.matchMedia(Q).matches,
    () => false,
  );
}
