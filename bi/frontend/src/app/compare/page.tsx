"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { Badge, Section, Table, errMsg, num, usd } from "@/components/panels/kit";
import { getJson } from "@/lib/api";
import type { CompareData } from "@/lib/types";

type Cell = number | string | null;
function fmt(v: Cell, unit: string): string {
  if (v == null) return "—";
  if (typeof v === "string") return v;
  return unit === "usd" ? usd(v) : unit === "pct" ? `${num(v, 1)}%` : num(v, 0);
}
const TONE: Record<string, "ok" | "warn" | "bad" | "muted"> = { good: "ok", warn: "warn", bad: "bad", nodata: "muted" };

export default function ComparePage() {
  const [d, setD] = useState<CompareData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<CompareData>("/api/compare", ctl.signal).then(setD).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't compare the workspaces.")); });
    return () => ctl.abort();
  }, []);
  return (
    <PageShell title="Practice vs Real" subtitle="The same measures side by side, so you can see what changes when the data is real.">
      {err && <ErrorBanner message={err} />}
      {!d && !err && <p className="text-sm text-muted">Comparing…</p>}
      {d && (
        <>
          <section className="card p-4 text-sm" aria-label="Reading this page"><p>{d.note}</p>{Object.entries(d.errors).map(([w, m]) => <p key={w} className="mt-1 text-red-600">Couldn&apos;t read the {w} database: {m}</p>)}</section>
          <Section title="Headline measures" note="Change is Real compared with Practice. Both files are only read: the one that isn't active is copied first.">
            <Table head={["Measure", "Practice", "Real", "Change"]} rows={d.metrics.map((m) => [m.label, fmt(m.practice, m.unit), fmt(m.real, m.unit),
              m.delta ? `${m.delta.abs > 0 ? "+" : ""}${m.unit === "usd" ? usd(m.delta.abs) : num(m.delta.abs, 1)}${m.delta.pct != null ? ` (${m.delta.pct > 0 ? "+" : ""}${m.delta.pct}%)` : ""}` : "—"])} />
          </Section>
          <Section title="Your KPIs on both datasets" note={d.kpi_note}>
            {d.kpis.length === 0 ? <p className="text-sm text-muted">No KPIs defined yet. Add some on the KPIs page and they will be scored against both datasets here.</p> : (
              <Table head={["KPI", "Target", "Practice", "Real"]} rows={d.kpis.map((k) => [k.name, `${k.direction === "higher" ? "≥" : "≤"} ${num(k.target, 2)}`,
                k.practice ? <span key="p"><Badge tone={TONE[k.practice.status]}>{k.practice.status}</Badge> {num(k.practice.value, 2)}</span> : "—",
                k.real ? <span key="r"><Badge tone={TONE[k.real.status]}>{k.real.status}</Badge> {num(k.real.value, 2)}</span> : "—"])} />
            )}
          </Section>
          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Tables"><Table head={["Table", "Practice rows", "Real rows"]} rows={d.tables.map((t) => [t.table, t.practice == null ? "—" : t.practice.toLocaleString(), t.real == null ? "—" : t.real.toLocaleString()])} /></Section>
            <Section title="Top entities by revenue">
              <div className="grid gap-3 sm:grid-cols-2">
                {(["practice", "real"] as const).map((w) => (
                  <div key={w}><div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{w}</div>
                    {d.top_entities[w].length === 0 ? <p className="text-sm text-muted">No data.</p> : <ol className="space-y-0.5 text-sm">{d.top_entities[w].map((e) => <li key={e.name}>{e.name} <span className="text-muted">{usd(e.revenue)}</span></li>)}</ol>}</div>
                ))}
              </div>
            </Section>
          </div>
          {d.schema_differences.length > 0 && (
            <Section title="Schema differences" note="Columns that exist in one workspace and not the other. Your queries and imports may behave differently.">
              <ul className="space-y-1 text-sm">{d.schema_differences.map((s) => <li key={s.table}><b>{s.table}</b>: only in Practice: {s.only_practice.join(", ") || "none"}; only in Real: {s.only_real.join(", ") || "none"}</li>)}</ul>
            </Section>
          )}
        </>
      )}
    </PageShell>
  );
}
