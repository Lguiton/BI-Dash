"use client";
import { useStoredJson } from "@/lib/useStoredJson";

/** The job you are working on right now. It stays pinned on every page until you unpin it. Kept in this browser only. */
export function useActiveJob(): [number | null, (id: number | null) => void] {
  return useStoredJson<number | null>("bi.activeJob", null);
}
