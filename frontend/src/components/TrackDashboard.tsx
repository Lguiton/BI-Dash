"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { DatasetStrip } from "@/components/DatasetCard";
import { BookOpen, FileCode, LayoutDashboard } from "lucide-react";
import { Suspense, useCallback, useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Bar, BarChart } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { PipelinePanel } from "@/components/PipelinePanel";
import { PmPanel } from "@/components/panels/PmPanel";
import { FullStackPanel } from "@/components/panels/FullStackPanel";
import { SaPanel } from "@/components/panels/SaPanel";
import { DbaPanel, GovernancePanel } from "@/components/panels/DbaGovPanels";
import { Tabs } from "@/components/panels/kit";
import { AgentPanel, CommandBar, useAgentChat } from "@/components/panels/AgentUi";
import { SecPanel } from "@/components/panels/SecPanel";
import { NetPanel } from "@/components/panels/NetPanel";
import { ItPanel } from "@/components/panels/ItPanel";
import { ManualPanel } from "@/components/panels/ManualPanel";
import { ApiError, getJson, putJson } from "@/lib/api";
import { money, pct } from "@/lib/format";
import { useChartColors } from "@/lib/useChartColors";
import type { AgentAction, ManualStep, AiDash, AnalystDash, EngineeringDash, MlDash, Progress, ScientistDash, Track, TrackStep } from "@/lib/types";

type Dash = { ideas: string[] } & Record<string, unknown>;
const DEFAULT_TAB: Record<string, string> = { pm: "board", sysanalyst: "req", fullstack: "api", security: "audit", network: "subnet", itsupport: "tickets", engineering: "pipeline" };
const OPEN_LAB: Record<string, { href: string; label: string }[]> = {
  analyst: [{ href: "/lab", label: "SQL Lab" }, { href: "/kpis", label: "KPI builder" }, { href: "/quality", label: "Data quality" }],
  scientist: [{ href: "/python", label: "Notebooks" }, { href: "/ml", label: "ML Lab" }],
  ml: [{ href: "/ml", label: "ML Lab" }, { href: "/python", label: "Notebooks 13-15" }],
  engineering: [{ href: "/pipeline", label: "Pipeline monitor" }, { href: "/apache", label: "Apache lab" }],
  ai: [{ href: "/ai", label: "AI Lab" }, { href: "/glossary", label: "Glossary" }],
  fullstack: [{ href: "/lab", label: "SQL Lab" }, { href: "/schema", label: "Schema" }, { href: "/activity", label: "Activity log" }],
  security: [{ href: "/activity", label: "Activity log" }, { href: "/settings", label: "Settings & backups" }],
  network: [{ href: "/activity", label: "Activity log" }, { href: "/settings", label: "Settings & backups" }],
  itsupport: [{ href: "/activity", label: "Activity log" }, { href: "/settings", label: "Settings & backups" }],
  pm: [{ href: "/kpis", label: "KPI builder" }, { href: "/activity", label: "Activity log" }],
  sysanalyst: [{ href: "/schema", label: "Schema" }, { href: "/quality", label: "Data quality" }, { href: "/lab", label: "SQL Lab" }],
};

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return <div className="card p-4"><div className="text-xs uppercase tracking-wide text-muted">{label}</div><div className="text-2xl font-bold tabular-nums">{value}</div>{sub && <div className="text-xs text-muted">{sub}</div>}</div>;
}
function Unavailable({ reason }: { reason: string }) { return <p className="text-sm text-muted">{reason}</p>; }

function AnalystPanels({ d }: { d: AnalystDash }) {
  const c = useChartColors();
  const k = d.kpis;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Net margin" value={pct(k.margin_pct)} sub="profit ÷ revenue (ratio of sums)" />
        <Stat label="Cost vs budget" value={k.vs_budget_pct == null ? "—" : `${k.vs_budget_pct > 0 ? "+" : ""}${k.vs_budget_pct.toFixed(1)}%`} sub="positive = over budget" />
        <Stat label="Completion" value={pct(k.completion_pct)} sub="status = Completed" />
        <Stat label="Data quality" value={`${d.quality.score_pct}%`} sub={d.quality.failing.length ? `Check: ${d.quality.failing[0]}` : `${d.quality.passed}/${d.quality.total} checks pass`} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-4">
          <h3 className="mb-2 text-sm font-semibold">Weekly net margin %</h3>
          <div className="h-56" role="img" aria-label="Line chart of weekly net margin percent">
            <ResponsiveContainer width="100%" height="100%" minWidth={200}>
              <LineChart data={d.weekly_margin} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
                <XAxis dataKey="week" stroke={c.axis} fontSize={11} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis stroke={c.axis} fontSize={11} width={40} domain={["auto", "auto"]} tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
                <Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} formatter={(v) => [`${Number(v).toFixed(1)}%`, "Margin"]} />
                <Line type="monotone" dataKey="margin_pct" stroke={c.profit} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="card overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="px-4 pt-3 text-left text-sm font-semibold">Most over budget</caption>
            <thead><tr><th className="th">Entity</th><th className="th th-r">Over budget</th><th className="th th-r">Overspend</th></tr></thead>
            <tbody>{d.over_budget.map((r) => (
              <tr key={r.entity} className="border-t border-line"><td className="px-4 py-2">{r.entity}</td>
                <td className="px-4 py-2 text-right tabular-nums">{r.vs_budget_pct > 0 ? "+" : ""}{r.vs_budget_pct.toFixed(1)}%</td>
                <td className="px-4 py-2 text-right tabular-nums">{money(r.overspend_usd, false)}</td></tr>))}</tbody>
          </table>
        </section>
      </div>
    </div>
  );
}

function ScientistPanels({ d }: { d: ScientistDash }) {
  const w = d.weekend_test, s = d.segments, cr = d.correlations;
  return (
    <div className="space-y-4">
      <section className="card p-4">
        <h3 className="mb-2 text-sm font-semibold">Is the weekend premium real? (Welch t-test on daily totals)</h3>
        {w.available ? (
          <div className="grid gap-3 text-sm sm:grid-cols-4">
            <Stat label="Weekend avg / day" value={money(w.weekend_mean, false)} sub={`${w.weekend_days} days`} />
            <Stat label="Weekday avg / day" value={money(w.weekday_mean, false)} sub={`${w.weekday_days} days`} />
            <Stat label="Difference" value={money(w.diff, false)} sub={`95% CI ${money(w.ci_low, false)} to ${money(w.ci_high, false)}`} />
            <Stat label="p-value" value={w.p_value < 0.001 ? "< 0.001" : w.p_value.toFixed(3)} sub={w.verdict} />
          </div>
        ) : <Unavailable reason={w.reason} />}
        <p className="mt-2 text-xs text-muted">Each day is one data point, not each record: records from the same day are not independent (pseudo-replication).</p>
      </section>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-4">
          <h3 className="mb-2 text-sm font-semibold">Entity segments (KMeans, k=3)</h3>
          {s.available ? (
            <ul className="space-y-2 text-sm">{s.segments.map((g) => (
              <li key={g.segment} className="rounded-lg bg-panel2 p-3"><b>Segment {g.segment}</b> <span className="text-muted">({g.entities.length})</span>
                <div className="text-xs">{g.entities.join(", ")}</div>
                <div className="mt-1 text-xs text-muted">margin {pct(g.means.margin * 100)} · cost ratio {g.means.cost_ratio.toFixed(2)} · completion {pct(g.means.completion * 100)} · avg revenue {money(g.means.avg_revenue, false)}</div></li>))}</ul>
          ) : <Unavailable reason={s.reason} />}
        </section>
        <section className="card overflow-x-auto p-4">
          <h3 className="mb-2 text-sm font-semibold">Correlations (Pearson)</h3>
          {cr.available ? (
            <table className="text-xs" aria-label="Correlation matrix">
              <thead><tr><th />{cr.names.map((n) => <th key={n} className="px-2 py-1 font-medium text-muted">{n.replace("_", " ")}</th>)}</tr></thead>
              <tbody>{cr.matrix.map((row, i) => (
                <tr key={cr.names[i]}><th scope="row" className="pr-2 text-left font-medium text-muted">{cr.names[i].replace("_", " ")}</th>
                  {row.map((v, j) => <td key={j} className="px-2 py-1.5 text-center tabular-nums" style={{ background: v == null ? undefined : `color-mix(in srgb, var(--accent) ${Math.round(Math.abs(v) * 55)}%, transparent)` }}>{v == null ? "n/a" : v.toFixed(2)}</td>)}</tr>))}</tbody>
            </table>
          ) : <Unavailable reason={cr.reason} />}
          <p className="mt-2 text-xs text-muted">Strong correlation is not causation, and revenue vs cost is strong partly by construction.</p>
        </section>
      </div>
    </div>
  );
}

function MlPanels({ d }: { d: MlDash }) {
  return (
    <div className="space-y-4">
      {d.total_runs === 0 ? (
        <div className="card p-4 text-sm">No experiments yet. Open the <Link href="/ml" className="underline">ML Lab</Link> and train a model: every run is logged here so you can see what actually helped.</div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            {d.best.map((b) => <Stat key={b.task} label={`Best: ${b.task.replace("_", " ")}`} value={`${b.metric.toUpperCase()} ${b.model_score?.toFixed(3)}`} sub={`${b.model} · baseline ${b.baseline_score?.toFixed(3)} · lift ${b.lift != null && b.lift > 0 ? "+" : ""}${b.lift}`} />)}
          </div>
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="px-4 pt-3 text-left text-sm font-semibold">Experiment log ({d.total_runs} runs)</caption>
              <thead><tr><th className="th">When</th><th className="th">Task</th><th className="th">Model</th><th className="th">Features</th><th className="th th-r">Score</th><th className="th th-r">Baseline</th></tr></thead>
              <tbody>{d.runs.map((r, i) => (
                <tr key={i} className="border-t border-line"><td className="px-4 py-2 whitespace-nowrap">{r.created_at}</td><td className="px-4 py-2">{r.task.replace("_", " ")}</td>
                  <td className="px-4 py-2">{r.model}</td><td className="px-4 py-2 text-xs text-muted">{r.features.length} features</td>
                  <td className="px-4 py-2 text-right tabular-nums">{r.metric.toUpperCase()} {r.model_score?.toFixed(3)}</td><td className="px-4 py-2 text-right tabular-nums text-muted">{r.baseline_score?.toFixed(3)}</td></tr>))}</tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function AiPanels({ d }: { d: AiDash }) {
  const c = useChartColors();
  const t = d.log.totals;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {d.providers.map((p) => {
          const ok = p.configured && p.sdk_installed;
          return <Stat key={p.id} label={p.label} value={ok ? `${p.used_today}/${p.daily_limit}` : "not set up"} sub={ok ? `${p.model} · today` : `add ${p.key_env} to backend/.env`} />;
        })}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-4 text-sm">
          <h3 className="mb-2 font-semibold">Usage so far</h3>
          <p>{t.questions} questions · {t.charts} charts · {(t.tin + t.tout).toLocaleString()} tokens</p>
          {d.log.by_provider.length > 0 && (
            <div className="mt-2 h-28" role="img" aria-label="Questions per provider">
              <ResponsiveContainer width="100%" height="100%" minWidth={150}>
                <BarChart data={d.log.by_provider} layout="vertical" margin={{ left: 8, right: 8 }}>
                  <XAxis type="number" hide /><YAxis type="category" dataKey="provider" stroke={c.axis} fontSize={11} width={70} /><Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} />
                  <Bar dataKey="questions" fill={c.revenue} radius={3} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
        <section className="card p-4 text-sm">
          <h3 className="mb-2 font-semibold">Recent questions</h3>
          {d.log.recent.length === 0 ? <p className="text-muted">None yet. Ask something in the <Link href="/ai" className="underline">AI Lab</Link>.</p> : (
            <ul className="space-y-1.5">{d.log.recent.map((r, i) => <li key={i}><span className="text-xs text-muted">{r.created_at.slice(5, 16)} · {r.provider} · {r.kind}</span><br />{r.question}</li>)}</ul>
          )}
        </section>
      </div>
    </div>
  );
}

function StepRow({ s, done, onToggle, onOpen }: { s: TrackStep; done: boolean; onToggle: () => void; onOpen: (s: TrackStep) => void }) {
  return (
    <li className="flex gap-2.5 text-sm">
      <input type="checkbox" className="mt-1 h-4 w-4 shrink-0" checked={done} onChange={onToggle} aria-label={`Mark "${s.label}" ${done ? "not done" : "done"}`} />
      <div className="min-w-0">
        {s.kind === "file" ? (
          <button className="inline-flex items-start gap-1.5 text-left font-medium underline decoration-dotted [overflow-wrap:anywhere]" onClick={() => onOpen(s)}><FileCode className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> {s.label}</button>
        ) : (
          <Link href={s.href ?? "/"} className="inline-flex items-center gap-1.5 font-medium underline decoration-dotted">
            {s.kind === "notebook" ? <BookOpen className="h-4 w-4" aria-hidden /> : <LayoutDashboard className="h-4 w-4" aria-hidden />}{s.label}{s.kind === "notebook" ? " (notebook)" : ""}
          </Link>
        )}
        <p className={`text-xs ${done ? "text-muted line-through" : "text-muted"}`}>{s.why}</p>
      </div>
    </li>
  );
}

function EngineeringTabs({ d, tab, onTab }: { d: EngineeringDash; tab: string; onTab: (t: string) => void }) {
  const [top, sub = "catalog"] = tab.split("/");
  return (
    <div className="space-y-4">
      <Tabs label="Data engineering areas" value={top} onChange={onTab} tabs={[{ id: "pipeline", label: "Pipeline" }, { id: "dba", label: "Database admin" }, { id: "gov", label: "Data governance" }]} />
      {top === "pipeline" && <PipelinePanel initial={d.pipeline} key={JSON.stringify(d.pipeline.history[0] ?? 0)} />}
      {top === "dba" && <DbaPanel />}
      {top === "gov" && <GovernancePanel tab={sub} onTab={(t) => onTab(`gov/${t}`)} />}
    </div>
  );
}

type TrackId = "analyst" | "scientist" | "ml" | "engineering" | "ai" | "pm" | "sysanalyst" | "fullstack" | "security" | "network" | "itsupport";
const parseView = (v: string | null): "manual" | "tools" | "agent" | null => (v === "manual" || v === "tools" || v === "agent" ? v : null);

/** Search results and agent links can open a track straight on a view, tab or manual step: /tracks/pm?view=manual&step=okr */
export function TrackDashboard({ id }: { id: TrackId }) {
  return <Suspense fallback={null}><TrackDashboardInner id={id} /></Suspense>;
}

function TrackDashboardInner({ id }: { id: TrackId }) {
  const sp = useSearchParams();
  const reqKey = sp.toString();
  const [seenReq, setSeenReq] = useState(reqKey);
  const [track, setTrack] = useState<Track | null>(null);
  const [dash, setDash] = useState<Dash | null>(null);
  const [prog, setProg] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<{ path: string; content: string } | null>(null);
  const [view, setView] = useState<"manual" | "tools" | "agent">(() => parseView(sp.get("view")) ?? "manual");
  const [tab, setTab] = useState(() => sp.get("tab") ?? DEFAULT_TAB[id] ?? "");
  const [focusStep, setFocusStep] = useState<string | undefined>(() => sp.get("step") ?? undefined);
  const [agentName, setAgentName] = useState("agent");
  const [stepId, setStepId] = useState<string | undefined>(undefined);
  const router = useRouter();
  const chat = useAgentChat(id);
  if (reqKey !== seenReq) {                       // the address changed while this page stayed open (for example from the search box)
    setSeenReq(reqKey);
    const v = parseView(sp.get("view"));
    if (v) setView(v);
    if (sp.get("tab")) setTab(sp.get("tab") as string);
    setFocusStep(sp.get("step") ?? undefined);
  }

  const goTool = (t: { href: string | null; tab: string | null }) => {
    if (t.href) { router.push(t.href); return; }
    if (t.tab) setTab(t.tab);
    setView("tools");
  };
  const goAction = (a: AgentAction) => { if (a.href) router.push(a.href); else if (a.tab) { setTab(a.tab); setView("tools"); } };
  const askAbout = (s: ManualStep) => { setStepId(s.id); setView("agent"); void chat.send(s.ask || `Help me with step: ${s.title}`, s.id); };
  const sendFromBar = (text: string) => { setView("agent"); void chat.send(text, stepId); };

  const loadProgress = useCallback((signal?: AbortSignal) => getJson<Progress>("/api/progress", signal).then(setProg).catch(() => {}), []);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ name: string }>(`/api/agents/${id}`, ctl.signal).then((r) => setAgentName(r.name)).catch(() => {});
    const fail = (e: unknown) => { if (!ctl.signal.aborted) setError(e instanceof ApiError ? e.message : "Couldn't load this dashboard."); };
    getJson<{ tracks: Track[] }>("/api/tracks", ctl.signal).then((r) => setTrack(r.tracks.find((t) => t.id === id) ?? null)).catch(fail);
    getJson<Dash>(`/api/tracks/${id}/dashboard`, ctl.signal).then(setDash).catch(fail);
    loadProgress(ctl.signal);
    return () => ctl.abort();
  }, [id, loadProgress]);

  async function toggle(s: TrackStep) {
    const nowDone = !(prog?.done.includes(s.id));
    // optimistic: tick the box straight away, then confirm with the server (and roll back if it fails)
    setProg((p) => (p ? { ...p, done: nowDone ? [...p.done, s.id] : p.done.filter((x) => x !== s.id) } : p));
    try { await putJson("/api/progress", { item: s.id, done: nowDone }); await loadProgress(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Couldn't save progress."); await loadProgress(); }
  }
  async function open(s: TrackStep) {
    if (!s.path) return;
    try { setFile(await getJson<{ path: string; content: string }>(`/api/tracks/file?path=${encodeURIComponent(s.path)}`)); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Couldn't open that file."); }
  }

  const serverTp = prog?.tracks.find((t) => t.id === id);
  const tickedHere = track ? track.path.filter((s) => prog?.done.includes(s.id)).length : serverTp?.done ?? 0;
  const tp = serverTp && track ? { ...serverTp, done: tickedHere, pct: Math.round((100 * tickedHere) / (track.path.length || 1)) } : serverTp;
  return (
    <PageShell title={`${track?.name ?? "Career"} dashboard`} subtitle={track?.role ?? "Your practice space for this career."}>
      {error && <ErrorBanner message={error} />}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Link href="/tracks" className="btn">All tracks</Link>
        <Link href="/company" className="btn">Company plan</Link>
        {OPEN_LAB[id].map((l) => <Link key={l.href} href={l.href} className="btn">{l.label}</Link>)}
        {tp && <span className="rounded-full bg-panel2 px-3 py-1 text-xs text-muted">{tp.done}/{tp.total} steps done ({tp.pct}%)</span>}
      </div>

      <CommandBar name={agentName} busy={chat.busy} onSend={sendFromBar} />

      <div role="tablist" aria-label="Workspace view" className="flex flex-wrap gap-1">
        {([["manual", "How-to manual"], ["tools", "Tools"], ["agent", "AI agent"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={view === k} className={`btn ${view === k ? "btn-primary" : ""}`} onClick={() => setView(k)}>{l}</button>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-4">
          {view === "manual" && <ManualPanel track={id} focus={focusStep} onGo={goTool} onAsk={askAbout} />}
          {view === "agent" && <AgentPanel track={id} chat={chat} onAction={goAction} />}
          {view === "tools" && (
            <>
              <DatasetStrip careerId={id} />
              {!dash && !error && <p className="text-sm text-muted">Loading…</p>}
              {dash && id === "analyst" && <AnalystPanels d={dash as unknown as AnalystDash} />}
              {dash && id === "scientist" && <ScientistPanels d={dash as unknown as ScientistDash} />}
              {dash && id === "ml" && <MlPanels d={dash as unknown as MlDash} />}
              {dash && id === "engineering" && <EngineeringTabs d={dash as unknown as EngineeringDash} tab={tab} onTab={setTab} />}
              {dash && id === "pm" && <PmPanel tab={tab} onTab={setTab} />}
              {dash && id === "sysanalyst" && <SaPanel tab={tab} onTab={setTab} />}
              {dash && id === "fullstack" && <FullStackPanel tab={tab} onTab={setTab} />}
              {dash && id === "security" && <SecPanel tab={tab} onTab={setTab} />}
              {dash && id === "network" && <NetPanel tab={tab} onTab={setTab} />}
              {dash && id === "itsupport" && <ItPanel tab={tab} onTab={setTab} />}
              {dash && id === "ai" && <AiPanels d={dash as unknown as AiDash} />}
              {dash && (
                <section className="card p-4">
                  <h3 className="mb-2 text-sm font-semibold">Build on it: practice ideas</h3>
                  <ul className="list-disc space-y-1 pl-5 text-sm">{dash.ideas.map((i) => <li key={i}>{i}</li>)}</ul>
                </section>
              )}
            </>
          )}
        </div>

        <aside className="card h-fit min-w-0 space-y-3 p-5">
          <h2 className="text-sm font-semibold">Learning path</h2>
          <ol className="space-y-3">
            {track?.path.map((s) => <StepRow key={s.id} s={s} done={!!prog?.done.includes(s.id)} onToggle={() => toggle(s)} onOpen={open} />)}
          </ol>
          {track && (
            <div>
              <h2 className="mb-1 mt-4 text-sm font-semibold">Portfolio projects</h2>
              <ul className="list-disc space-y-1 pl-5 text-xs text-muted">{track.projects.map((p) => <li key={p}>{p}</li>)}</ul>
            </div>
          )}
        </aside>
      </div>

      {file && (
        <section className="card min-w-0">
          <div className="flex items-center justify-between border-b border-line px-4 py-3 text-sm">
            <span className="font-mono text-xs">{file.path}</span><button className="btn" onClick={() => setFile(null)}>Close</button>
          </div>
          <pre className="max-h-[32rem] overflow-auto p-4 text-xs leading-relaxed" tabIndex={0}><code>{file.content}</code></pre>
        </section>
      )}
    </PageShell>
  );
}
