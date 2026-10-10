"use client";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { Section, Stat, Table, Tabs, bytes, errMsg } from "@/components/panels/kit";
import { API_BASE, getJson } from "@/lib/api";
import { useChartColors } from "@/lib/useChartColors";

interface Route { method: string; route: string; count: number; errors: number; avg_ms: number; p95_ms: number; max_ms: number }
interface Ops {
  uptime_seconds: number; requests: number; server_errors: number; error_rate_pct: number; slowest: Route[]; busiest: Route[]; failing: Route[];
  files: Record<string, number>; ai: { provider: string; calls: number; avg_seconds: number | null; max_seconds: number | null; tin: number; tout: number; failed: number }[];
  pipelines: { total: number; failing: number }; sources: { total: number; failing: number }; quality: { tables_failing: number }; alerts: { count: number }; note: string;
}
interface Llm {
  days: number; calls: number; providers: { provider: string; calls: number; failed: number; timed_calls: number; avg_s: number | null; p95_s: number | null; max_s: number | null; tokens_in: number; tokens_out: number; cost_usd: number | null }[];
  daily: { day: string; calls: number; tokens: number; avg_s: number | null }[]; slowest: { at: string; provider: string; model: string; seconds: number; tier: string; question: string }[]; total_cost_usd: number | null; note: string;
}
const dur = (s: number) => (s >= 3600 ? `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min` : s >= 60 ? `${Math.floor(s / 60)} min` : `${s} s`);
const routeRows = (r: Route[]) => r.map((x) => [`${x.method} ${x.route}`, x.count.toLocaleString(), `${x.avg_ms}`, `${x.p95_ms}`, `${x.max_ms}`, String(x.errors)]);

export default function OpsPage() {
  const [tab, setTab] = useState("api");
  const [o, setO] = useState<Ops | null>(null);
  const [l, setL] = useState<Llm | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  const c = useChartColors();
  useEffect(() => {
    const ctl = new AbortController();
    Promise.all([getJson<Ops>("/api/ops", ctl.signal), getJson<Llm>("/api/ops/llm?days=14", ctl.signal)]).then(([a, b]) => { setO(a); setL(b); setErr(null); })
      .catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the monitor.")); });
    return () => ctl.abort();
  }, [ver]);
  return (
    <PageShell title="Ops monitor" subtitle="How the app itself is doing: requests, slow endpoints, database files, scheduled work, and AI calls.">
      {err && <ErrorBanner message={err} />}
      {!o && !err && <p className="text-sm text-muted">Loading…</p>}
      {o && l && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Uptime" value={dur(o.uptime_seconds)} /><Stat label="Requests" value={o.requests.toLocaleString()} sub="since the backend started" />
            <Stat label="Server errors" value={String(o.server_errors)} sub={`${o.error_rate_pct}% of requests`} /><Stat label="Active alerts" value={String(o.alerts.count)} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Tabs tabs={[{ id: "api", label: "API" }, { id: "llm", label: "AI calls" }, { id: "work", label: "Data & jobs" }]} value={tab} onChange={setTab} label="Monitor views" />
            <button className="btn ml-auto" onClick={() => setVer((v) => v + 1)}>Refresh</button>
          </div>
          {tab === "api" && (
            <>
              <Section title="Slowest endpoints (by 95th percentile, ms)"><Table head={["Endpoint", "Calls", "Avg ms", "p95 ms", "Max ms", "Errors"]} rows={routeRows(o.slowest)} caption="Slowest endpoints" /></Section>
              <Section title="Busiest endpoints"><Table head={["Endpoint", "Calls", "Avg ms", "p95 ms", "Max ms", "Errors"]} rows={routeRows(o.busiest)} caption="Busiest endpoints" /></Section>
              {o.failing.length > 0 && <Section title="Endpoints with server errors"><Table head={["Endpoint", "Calls", "Avg ms", "p95 ms", "Max ms", "Errors"]} rows={routeRows(o.failing)} caption="Failing endpoints" /></Section>}
              <p className="text-xs text-muted">Prometheus can scrape <code>{API_BASE}/metrics</code> (text format) if you want Grafana dashboards. {o.note}</p>
            </>
          )}
          {tab === "llm" && (
            <>
              <div className="grid gap-3 sm:grid-cols-3"><Stat label={`Calls (${l.days} days)`} value={String(l.calls)} /><Stat label="Providers used" value={String(l.providers.length)} /><Stat label="Estimated cost" value={l.total_cost_usd == null ? "not set" : `$${l.total_cost_usd}`} sub={l.total_cost_usd == null ? "add BI_PRICE_* to .env" : undefined} /></div>
              <Section title="By provider"><Table head={["Provider", "Calls", "Failed", "Avg s", "p95 s", "Max s", "Tokens in", "Tokens out", "Cost"]} caption="AI calls by provider"
                rows={l.providers.map((p) => [p.provider, String(p.calls), String(p.failed), p.avg_s ?? "—", p.p95_s ?? "—", p.max_s ?? "—", p.tokens_in.toLocaleString(), p.tokens_out.toLocaleString(), p.cost_usd == null ? "—" : `$${p.cost_usd}`])} /></Section>
              {l.daily.length > 0 && (
                <Section title="Calls per day">
                  <div className="h-48" role="img" aria-label="Bar chart of AI calls per day"><ResponsiveContainer width="100%" height="100%"><BarChart data={l.daily}><CartesianGrid strokeDasharray="3 3" stroke={c.grid} /><XAxis dataKey="day" tick={{ fontSize: 11, fill: c.axis }} /><YAxis allowDecimals={false} tick={{ fontSize: 11, fill: c.axis }} /><Tooltip /><Bar dataKey="calls" fill={c.revenue} /></BarChart></ResponsiveContainer></div>
                </Section>
              )}
              {l.slowest.length > 0 && <Section title="Slowest calls"><Table head={["When", "Provider", "Model", "Seconds", "Question"]} caption="Slowest AI calls" rows={l.slowest.map((s) => [s.at, s.provider, s.model, String(s.seconds), s.question])} /></Section>}
              <p className="text-xs text-muted">{l.note}</p>
            </>
          )}
          {tab === "work" && (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Stat label="Pipelines" value={String(o.pipelines.total)} sub={`${o.pipelines.failing} failing`} /><Stat label="Sources" value={String(o.sources.total)} sub={`${o.sources.failing} failing`} />
                <Stat label="Tables failing rules" value={String(o.quality.tables_failing)} /><Stat label="State file" value={bytes(o.files.state ?? 0)} />
              </div>
              <Section title="Database files"><Table head={["Workspace", "Size"]} caption="Database file sizes" rows={Object.entries(o.files).map(([k, v]) => [k, bytes(v)])} /></Section>
            </>
          )}
        </>
      )}
    </PageShell>
  );
}
