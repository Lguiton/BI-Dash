"use client";
import { useEffect, useState, type ReactNode } from "react";
import { getJson } from "@/lib/api";
import type { WorkspaceList } from "@/lib/types";

export function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return <div className="card p-4"><div className="text-xs uppercase tracking-wide text-muted">{label}</div><div className="text-2xl font-bold tabular-nums">{value}</div>{sub && <div className="text-xs text-muted">{sub}</div>}</div>;
}
export const num = (v: number | null | undefined, d = 1) => (v == null || Number.isNaN(v) ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: d }));
export const usd = (v: number | null | undefined) => (v == null ? "—" : `$${Math.round(v).toLocaleString()}`);
export const bytes = (n: number) => (n >= 1e9 ? `${(n / 1e9).toFixed(2)} GB` : n >= 1e6 ? `${(n / 1e6).toFixed(2)} MB` : n >= 1e3 ? `${(n / 1e3).toFixed(1)} KB` : `${n} B`);

export function Tabs({ tabs, value, onChange, label }: { tabs: { id: string; label: string }[]; value: string; onChange: (id: string) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="flex flex-wrap gap-1">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)} className={`btn ${value === t.id ? "btn-primary" : ""}`}>{t.label}</button>
      ))}
    </div>
  );
}
export function Section({ title, children, note }: { title: string; children: ReactNode; note?: string }) {
  return <section className="card min-w-0 p-4"><h3 className="mb-2 text-sm font-semibold">{title}</h3>{children}{note && <p className="mt-2 text-xs text-muted">{note}</p>}</section>;
}
export function Table({ head, rows, caption }: { head: string[]; rows: ReactNode[][]; caption?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead><tr>{head.map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i} className="border-t border-line">{r.map((c, j) => <td key={j} className="td">{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="flex min-w-0 flex-col gap-1 text-xs text-muted">{label}{children}</label>;
}
export function Badge({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "ok" | "warn" | "bad" }) {
  const c = tone === "ok" ? "text-emerald-600" : tone === "warn" ? "text-amber-600" : tone === "bad" ? "text-red-600" : "text-muted";
  return <span className={`rounded-full bg-panel2 px-2 py-0.5 text-xs ${c}`}>{children}</span>;
}
/** True when the active workspace is Practice, where example data may be loaded. */
export function useIsPractice(): boolean {
  const [p, setP] = useState(true);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<WorkspaceList>("/api/workspaces", ctl.signal).then((w) => setP(w.active === "practice")).catch(() => {});
    return () => ctl.abort();
  }, []);
  return p;
}
export function errMsg(e: unknown, fallback: string): string {
  return e instanceof Error && e.message ? e.message : fallback;
}
