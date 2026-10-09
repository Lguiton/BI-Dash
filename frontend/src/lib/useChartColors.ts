"use client";
import { useSyncExternalStore } from "react";

export interface ChartColors {
  revenue: string;
  cost: string;
  profit: string;
  grid: string;
  axis: string;
  panel: string;
  line: string;
  fg: string;
}

const FALLBACK: ChartColors = {
  revenue: "#2563eb", cost: "#dc2626", profit: "#059669",
  grid: "#e2e8f0", axis: "#64748b", panel: "#ffffff", line: "#cbd5e1", fg: "#0f172a",
};

function read(): ChartColors {
  const s = getComputedStyle(document.documentElement);
  const g = (name: string, fb: string) => s.getPropertyValue(name).trim() || fb;
  return {
    revenue: g("--c-revenue", FALLBACK.revenue), cost: g("--c-cost", FALLBACK.cost),
    profit: g("--c-profit", FALLBACK.profit), grid: g("--grid", FALLBACK.grid),
    axis: g("--muted", FALLBACK.axis), panel: g("--panel", FALLBACK.panel),
    line: g("--line", FALLBACK.line), fg: g("--fg", FALLBACK.fg),
  };
}

// useSyncExternalStore needs a referentially stable snapshot while nothing changed.
let cache: ChartColors | null = null;
function getSnapshot(): ChartColors {
  const next = read();
  if (cache && (Object.keys(next) as (keyof ChartColors)[]).every((k) => cache![k] === next[k])) return cache;
  cache = next;
  return cache;
}

function subscribe(cb: () => void) {
  const mo = new MutationObserver(cb);
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", cb);
  return () => {
    mo.disconnect();
    mq.removeEventListener("change", cb);
  };
}

/** Chart palette read from the live CSS variables; follows the theme toggle and OS setting. */
export function useChartColors(): ChartColors {
  return useSyncExternalStore(subscribe, getSnapshot, () => FALLBACK);
}
