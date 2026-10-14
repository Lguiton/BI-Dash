"use client";

import { AlertTriangle, CheckCircle2, MinusCircle, Trash2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LineageButton } from "@/components/Lineage";
import { PageShell } from "@/components/PageShell";
import { ApiError, deleteJson, getJson, postJson } from "@/lib/api";
import type { Kpi, KpiStatus, MetricInfo } from "@/lib/types";

function fmt(unit: MetricInfo["unit"], v: number | null): string {
  if (v === null) return "n/a";
  if (unit === "usd") return `$${v.toLocaleString("en-US", { maximumFractionDigits: Math.abs(v) < 100 ? 2 : 0 })}`;
  if (unit === "pct") return `${v.toLocaleString("en-US", { maximumFractionDigits: 1 })}%`;
  if (unit === "min") return `${v.toLocaleString("en-US", { maximumFractionDigits: 1 })} min`;
  return v.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

const STATUS: Record<KpiStatus, { label: string; bg: string; fg: string; Icon: typeof CheckCircle2 }> = {
  good: { label: "On target", bg: "var(--good-bg)", fg: "var(--good)", Icon: CheckCircle2 },
  warn: { label: "Close", bg: "var(--warn-bg)", fg: "var(--fg)", Icon: AlertTriangle },
  bad: { label: "Off target", bg: "var(--bad-bg)", fg: "var(--bad)", Icon: XCircle },
  nodata: { label: "No data", bg: "var(--panel-2)", fg: "var(--muted)", Icon: MinusCircle },
};
const WINDOWS = [{ v: 7, l: "Last 7 days" }, { v: 30, l: "Last 30 days" }, { v: 90, l: "Last 90 days" }, { v: 0, l: "All data" }];

export default function KpiPage() {
  const [kpis, setKpis] = useState<Kpi[] | null>(null);
  const [metrics, setMetrics] = useState<MetricInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [metric, setMetric] = useState("revenue");
  const [direction, setDirection] = useState<"higher" | "lower">("higher");
  const [target, setTarget] = useState("");
  const [warn, setWarn] = useState("10");
  const [win, setWin] = useState(30);

  useEffect(() => {
    const ctl = new AbortController();
    Promise.all([
      getJson<{ kpis: Kpi[] }>("/api/kpis", ctl.signal),
      getJson<{ metrics: MetricInfo[] }>("/api/kpis/metrics", ctl.signal),
    ]).then(([k, m]) => { setKpis(k.kpis); setMetrics(m.metrics); setError(null); })
      .catch((e) => { if (!ctl.signal.aborted) setError(e instanceof ApiError ? e.message : "Couldn't load KPIs."); });
    return () => ctl.abort();
  }, [version]);

  const info = metrics.find((m) => m.id === metric);
  const refresh = () => setVersion((v) => v + 1);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await fn(); refresh(); } catch (e) { setError(e instanceof ApiError ? e.message : "Something went wrong."); } finally { setBusy(false); }
  }
  const create = () => run(async () => {
    await postJson("/api/kpis", { name: name.trim(), metric, direction, target: Number(target), warn_pct: Number(warn), window_days: win });
    setName(""); setTarget("");
  });

  return (
    <PageShell title="KPI builder" subtitle="A metric measures. A KPI ties a metric to a goal. Define targets and see which are on track.">
      <section className="card space-y-1 p-5 text-sm" aria-label="Concept">
        <p><b>Metric:</b> any measurement (revenue, margin). <b>KPI:</b> a metric + a <b>target</b> + a <b>direction</b> (higher or lower is better) + a <b>time window</b> + a <b>warning band</b>.</p>
        <p className="text-muted">Status: <b>On target</b> if the goal is met; <b>Close</b> if you miss it by less than the warning band; <b>Off target</b> otherwise. Windows end on the latest date in your data.</p>
      </section>

      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <section className="card p-5" aria-label="New KPI">
        <h2 className="text-lg font-semibold">Define a KPI</h2>
        <form className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3" onSubmit={(e) => { e.preventDefault(); void create(); }}>
          <label className="text-sm">Name
            <input className="field mt-1 block w-full" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} placeholder="e.g. Weekly revenue goal" required />
          </label>
          <label className="text-sm">Metric
            <select className="field mt-1 block w-full" value={metric} onChange={(e) => { setMetric(e.target.value); const m = metrics.find((x) => x.id === e.target.value); if (m) setDirection(m.default_direction); }}>
              {metrics.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </label>
          <label className="text-sm">Better when
            <select className="field mt-1 block w-full" value={direction} onChange={(e) => setDirection(e.target.value as "higher" | "lower")}>
              <option value="higher">Higher</option><option value="lower">Lower</option>
            </select>
          </label>
          <label className="text-sm">Target{info ? ` (${info.unit === "usd" ? "$" : info.unit === "pct" ? "%" : info.unit === "min" ? "minutes" : "count"})` : ""}
            <input className="field mt-1 block w-full" type="number" step="any" value={target} onChange={(e) => setTarget(e.target.value)} required />
          </label>
          <label className="text-sm">Warning band (% of target)
            <input className="field mt-1 block w-full" type="number" min={0} max={100} step="any" value={warn} onChange={(e) => setWarn(e.target.value)} required />
          </label>
          <label className="text-sm">Time window
            <select className="field mt-1 block w-full" value={win} onChange={(e) => setWin(Number(e.target.value))}>
              {WINDOWS.map((w) => <option key={w.v} value={w.v}>{w.l}</option>)}
            </select>
          </label>
          <div className="sm:col-span-2 lg:col-span-3">
            {info && <p className="mb-2 text-xs text-muted">{info.description}</p>}
            <button className="btn btn-primary" disabled={busy || !name.trim() || target === ""}>Add KPI</button>
          </div>
        </form>
      </section>

      <section aria-label="Your KPIs">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide">Your KPIs</h2>
        {!kpis && !error && <p className="text-sm text-muted">Loading…</p>}
        {kpis && kpis.length === 0 && (
          <div className="card flex flex-wrap items-center justify-between gap-3 p-5">
            <p className="text-sm text-muted">No KPIs yet. Add one above, or start with three examples built from your current data.</p>
            <button className="btn" disabled={busy} onClick={() => run(() => postJson("/api/kpis/examples", {}))}>Add starter KPIs</button>
          </div>
        )}
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {kpis?.map((k) => {
            const st = STATUS[k.status];
            const delta = k.value !== null && k.previous_value ? ((k.value - k.previous_value) / Math.abs(k.previous_value)) * 100 : null;
            return (
              <li key={k.id} className="card flex flex-col gap-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-semibold">{k.name}</h3>
                    <p className="text-xs text-muted">{k.label} · {k.window_days === 0 ? "all data" : `last ${k.window_days} days`}</p>
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold" style={{ background: st.bg, color: st.fg }}>
                    <st.Icon className="h-3.5 w-3.5" aria-hidden /> {st.label}
                  </span>
                </div>
                <div className="text-3xl font-bold tabular-nums">{fmt(k.unit, k.value)}</div>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <dt className="text-muted">Target ({k.direction === "higher" ? "at least" : "at most"})</dt><dd className="text-right font-medium tabular-nums">{fmt(k.unit, k.target)}</dd>
                  <dt className="text-muted">Gap to target</dt><dd className="text-right font-medium tabular-nums">{k.gap === null ? "n/a" : `${k.gap > 0 ? "+" : k.gap < 0 ? "−" : ""}${fmt(k.unit, Math.abs(k.gap))}`}</dd>
                  {k.window_days > 0 && (<><dt className="text-muted">Previous window</dt><dd className="text-right tabular-nums">{fmt(k.unit, k.previous_value)}{delta !== null && ` (${delta > 0 ? "+" : ""}${delta.toFixed(1)}%)`}</dd></>)}
                </dl>
                <LineageButton kpiId={k.id} />
                <button className="btn mt-auto self-start !px-2 !py-1 text-xs" disabled={busy} onClick={() => run(() => deleteJson(`/api/kpis/${k.id}`))} aria-label={`Delete ${k.name}`}>
                  <Trash2 className="h-3.5 w-3.5" aria-hidden /> Delete
                </button>
              </li>
            );
          })}
        </ul>
      </section>
    </PageShell>
  );
}
