"use client";
import { useCallback, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, AreaChart } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, patchJson, postJson } from "@/lib/api";
import { useChartColors } from "@/lib/useChartColors";
import type { PmOverview, PmProduct } from "@/lib/types";
import { TimePanel } from "./OpsPanels";
import { CalendarTab, RulesTab } from "./PmExtras";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg, num, useIsPractice, usd } from "./kit";

const TABS = [
  { id: "board", label: "Board" }, { id: "prio", label: "Prioritisation" }, { id: "sprint", label: "Sprints" }, { id: "flow", label: "Flow" },
  { id: "schedule", label: "Schedule" }, { id: "evm", label: "Earned value" }, { id: "risk", label: "Risks" }, { id: "okr", label: "OKRs" }, { id: "product", label: "Product analytics" }, { id: "time", label: "Time" },
  { id: "calendar", label: "Calendar" }, { id: "rules", label: "Automations" },
];

export function PmPanel({ tab, onTab }: { tab: string; onTab: (t: string) => void }) {
  const [d, setD] = useState<PmOverview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const practice = useIsPractice();
  const [ver, setVer] = useState(0);
  const load = useCallback(async () => { setVer((v) => v + 1); }, []);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<PmOverview>("/api/pm", ctl.signal).then((r) => { setD(r); setErr(null); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the project data.")); });
    return () => ctl.abort();
  }, [ver]);
  const act = async (fn: () => Promise<unknown>) => { try { await fn(); await load(); } catch (e) { setErr(errMsg(e, "That didn't save.")); } };

  if (!d) return <>{err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>}</>;
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-center gap-2">
        <Tabs tabs={TABS} value={tab} onChange={onTab} label="Project and product views" />
        {d.empty && practice && <button className="btn" onClick={() => act(() => postJson("/api/pm/example", {}))}>Load example project</button>}
      </div>
      {d.empty && tab !== "product" && tab !== "risk" && tab !== "okr" && (
        <p className="card p-4 text-sm text-muted">No work items yet in this workspace. Add one below{practice ? ", or load the example project to see every view filled in" : ""}. Nothing here is made up: every number is computed from the items, sprints, risks and OKRs you enter.</p>
      )}
      {tab === "board" && <Board d={d} act={act} />}
      {tab === "prio" && <Prio d={d} />}
      {tab === "sprint" && <Sprints d={d} act={act} />}
      {tab === "flow" && <Flow d={d} />}
      {tab === "schedule" && <Schedule d={d} />}
      {tab === "evm" && <Evm d={d} />}
      {tab === "risk" && <Risks d={d} act={act} />}
      {tab === "okr" && <Okrs d={d} act={act} />}
      {tab === "product" && <Product />}
      {tab === "time" && <TimePanel items={d.items} onChanged={load} />}
      {tab === "calendar" && <CalendarTab />}
      {tab === "rules" && <RulesTab onChanged={load} />}
    </div>
  );
}
type Act = (fn: () => Promise<unknown>) => Promise<void>;

function Board({ d, act }: { d: PmOverview; act: Act }) {
  const [f, setF] = useState({ title: "", kind: "task", sprint_id: "", points: "", owner: "", reach: "", impact: "", confidence: "", effort: "", value: "", time_crit: "", risk_red: "", moscow: "", start_date: "", duration_days: "", deps: "", planned_cost: "", actual_cost: "" });
  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const add = () => act(async () => { await postJson("/api/pm/items", Object.fromEntries(Object.entries(f).filter(([, v]) => v !== ""))); setF({ ...f, title: "" }); });
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-5">
        {d.enums.statuses.map((s) => (
          <section key={s} className="card min-w-0 p-3" aria-label={`${s} column`}>
            <h3 className="mb-2 flex justify-between text-xs font-semibold uppercase tracking-wide text-muted"><span>{s}</span><span>{d.counts[s] ?? 0}</span></h3>
            <ul className="space-y-2">
              {d.items.filter((i) => i.status === s).map((i) => (
                <li key={i.id} className="rounded-md border border-line bg-panel2 p-2 text-xs">
                  <div className="font-medium">{i.title}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-1 text-muted"><Badge>{i.kind}</Badge>{i.points != null && <span>{i.points} pts</span>}{i.owner && <span>{i.owner}</span>}</div>
                  <div className="mt-2 flex items-center gap-1">
                    <select aria-label={`Move ${i.title}`} className="field !py-0.5 text-xs" value={i.status} onChange={(e) => act(() => patchJson(`/api/pm/items/${i.id}`, { status: e.target.value }))}>
                      {d.enums.statuses.map((x) => <option key={x}>{x}</option>)}
                    </select>
                    <button className="btn !px-2 !py-0.5 text-xs" aria-label={`Delete ${i.title}`} onClick={() => act(() => deleteJson(`/api/pm/items/${i.id}`))}>×</button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
      <Section title="Add a work item" note="RICE needs reach, impact, confidence (0–1) and effort. WSJF needs value, time criticality, risk reduction and points. Schedule and earned value need start date, duration and cost; dependencies are item ids like 3, 5.">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Title"><input className="field" value={f.title} onChange={set("title")} /></Field>
          <Field label="Kind"><select className="field" value={f.kind} onChange={set("kind")}>{d.enums.kinds.map((k) => <option key={k}>{k}</option>)}</select></Field>
          <Field label="Owner"><input className="field" value={f.owner} onChange={set("owner")} /></Field>
          <Field label="Sprint"><select className="field" value={f.sprint_id} onChange={set("sprint_id")}><option value="">none</option>{d.sprint.sprints.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
          <Field label="MoSCoW"><select className="field" value={f.moscow} onChange={set("moscow")}><option value="">—</option>{d.enums.moscow.map((k) => <option key={k}>{k}</option>)}</select></Field>
          {(["points", "reach", "impact", "confidence", "effort", "value", "time_crit", "risk_red", "duration_days", "planned_cost", "actual_cost"] as const).map((k) => (
            <Field key={k} label={k.replace("_", " ")}><input className="field" inputMode="decimal" value={f[k]} onChange={set(k)} /></Field>
          ))}
          <Field label="Start date"><input className="field" type="date" value={f.start_date} onChange={set("start_date")} /></Field>
          <Field label="Depends on (ids)"><input className="field" value={f.deps} onChange={set("deps")} /></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={!f.title.trim()} onClick={add}>Add item</button>
      </Section>
    </div>
  );
}

function Prio({ d }: { d: PmOverview }) {
  const p = d.prioritization;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        {(["must", "should", "could", "wont"] as const).map((k) => <Stat key={k} label={k} value={`${p.moscow[k]?.items ?? 0} items`} sub={`${num(p.moscow[k]?.points ?? 0, 0)} pts`} />)}
      </div>
      <Section title="RICE and WSJF ranking" note={`RICE = reach × impact × confidence ÷ effort. WSJF = (value + time criticality + risk reduction) ÷ points. ${p.unscored} item(s) lack the inputs for either score. ${p.must_share_pct != null ? `Must-haves are ${p.must_share_pct}% of classified points (a common guideline is to stay near 60%).` : ""}`}>
        <Table caption="Prioritisation scores" head={["#", "Item", "Status", "MoSCoW", "Points", "RICE", "WSJF"]}
          rows={p.rows.map((r, i) => [i + 1, r.title, r.status, r.moscow ?? "—", num(r.points), num(r.rice), num(r.wsjf)])} />
      </Section>
    </div>
  );
}

function Sprints({ d, act }: { d: PmOverview; act: Act }) {
  const c = useChartColors();
  const s = d.sprint;
  const [f, setF] = useState({ name: "", start_date: "", end_date: "", goal: "" });
  const bd = s.burndown;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Velocity (last 3)" value={num(s.velocity.avg_last3)} sub="average completed points per finished sprint" />
        <Stat label="Sprints" value={String(s.sprints.length)} />
        <Stat label="Likely finish" value={s.forecast?.likely.date ?? "—"} sub={s.forecast ? `${num(s.forecast.remaining_points, 0)} pts left · ${s.forecast.likely.sprints} sprints` : "needs ≥1 finished sprint"} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Velocity by sprint">
          <div className="h-56" role="img" aria-label="Bar chart of committed and completed points per sprint">
            <ResponsiveContainer width="100%" height="100%" minWidth={200}>
              <BarChart data={s.sprints}><CartesianGrid strokeDasharray="3 3" stroke={c.grid} /><XAxis dataKey="name" stroke={c.axis} fontSize={11} /><YAxis stroke={c.axis} fontSize={11} width={32} />
                <Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} /><Legend />
                <Bar dataKey="committed" fill={c.axis} /><Bar dataKey="completed" fill={c.profit} /></BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
        <Section title={bd ? `Burndown: ${bd.sprint}` : "Burndown"} note={bd?.status}>
          {bd ? (
            <div className="h-56" role="img" aria-label="Line chart of ideal versus actual remaining points">
              <ResponsiveContainer width="100%" height="100%" minWidth={200}>
                <LineChart data={bd.points}><CartesianGrid strokeDasharray="3 3" stroke={c.grid} /><XAxis dataKey="day" stroke={c.axis} fontSize={11} tickFormatter={(v: string) => v.slice(5)} /><YAxis stroke={c.axis} fontSize={11} width={32} />
                  <Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} /><Legend />
                  <Line dataKey="ideal" stroke={c.axis} strokeDasharray="4 4" dot={false} /><Line dataKey="actual" stroke={c.revenue} strokeWidth={2} dot={false} connectNulls={false} /></LineChart>
              </ResponsiveContainer>
            </div>
          ) : <p className="text-sm text-muted">No sprint contains items yet.</p>}
        </Section>
      </div>
      {s.forecast && <Section title="Delivery forecast" note={s.forecast.note}>
        <Table head={["Scenario", "Sprints", "Finish"]} rows={[["Fast", s.forecast.fast.sprints, s.forecast.fast.date], ["Likely", s.forecast.likely.sprints, s.forecast.likely.date], ["Slow", s.forecast.slow.sprints, s.forecast.slow.date]]} />
      </Section>}
      <Section title="Sprints">
        <Table head={["Sprint", "Dates", "Goal", "Committed", "Completed", "Done", ""]}
          rows={s.sprints.map((x) => [x.name, `${x.start_date} → ${x.end_date}`, x.goal ?? "", x.committed, x.completed, `${num(x.completion_pct, 0)}%`,
            <button key={x.id} className="btn !py-0.5 text-xs" onClick={() => act(() => deleteJson(`/api/pm/sprints/${x.id}`))}>Delete</button>])} />
        <div className="mt-3 grid gap-2 sm:grid-cols-4">
          <Field label="Name"><input className="field" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <Field label="Start"><input className="field" type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} /></Field>
          <Field label="End"><input className="field" type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} /></Field>
          <Field label="Goal"><input className="field" value={f.goal} onChange={(e) => setF({ ...f, goal: e.target.value })} /></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={!f.name || !f.start_date || !f.end_date} onClick={() => act(async () => { await postJson("/api/pm/sprints", f); setF({ name: "", start_date: "", end_date: "", goal: "" }); })}>Add sprint</button>
        <p className="mt-2 text-xs text-muted">Choose the sprint when adding a work item. Committed points are those assigned; completed points are the ones marked done.</p>
      </Section>
    </div>
  );
}

function Flow({ d }: { d: PmOverview }) {
  const c = useChartColors();
  const f = d.flow;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Cycle time (median)" value={`${num(f.cycle_days.median)} d`} sub={`p85 ${num(f.cycle_days.p85)} d · n=${f.cycle_days.n}`} />
        <Stat label="Lead time (median)" value={`${num(f.lead_days.median)} d`} sub={`p85 ${num(f.lead_days.p85)} d · n=${f.lead_days.n}`} />
        <Stat label="WIP now" value={String(f.wip)} sub={`Little's law expects ${num(f.littles_law.expected_wip)}`} />
        <Stat label="Throughput" value={`${num(f.littles_law.throughput_per_day, 2)}/day`} sub={`${f.done_count} items done`} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Cumulative flow (30 days)" note="Parallel bands mean steady flow. A widening 'doing' band means work is piling up faster than it finishes.">
          <div className="h-56" role="img" aria-label="Cumulative flow diagram">
            <ResponsiveContainer width="100%" height="100%" minWidth={200}>
              <AreaChart data={f.cfd}><CartesianGrid strokeDasharray="3 3" stroke={c.grid} /><XAxis dataKey="day" stroke={c.axis} fontSize={11} tickFormatter={(v: string) => v.slice(5)} /><YAxis stroke={c.axis} fontSize={11} width={32} />
                <Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} /><Legend />
                <Area dataKey="done" stackId="1" stroke={c.profit} fill={c.profit} fillOpacity={0.5} /><Area dataKey="doing" stackId="1" stroke={c.revenue} fill={c.revenue} fillOpacity={0.5} /><Area dataKey="todo" stackId="1" stroke={c.axis} fill={c.axis} fillOpacity={0.3} /></AreaChart>
            </ResponsiveContainer>
          </div>
        </Section>
        <Section title="Throughput per week">
          <div className="h-56" role="img" aria-label="Bar chart of items finished per week">
            <ResponsiveContainer width="100%" height="100%" minWidth={200}>
              <BarChart data={f.throughput_weekly}><CartesianGrid strokeDasharray="3 3" stroke={c.grid} /><XAxis dataKey="week" stroke={c.axis} fontSize={11} tickFormatter={(v: string) => v.slice(5)} /><YAxis stroke={c.axis} fontSize={11} width={32} allowDecimals={false} />
                <Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} /><Bar dataKey="done" fill={c.revenue} /></BarChart>
            </ResponsiveContainer>
          </div>
        </Section>
      </div>
    </div>
  );
}

function Schedule({ d }: { d: PmOverview }) {
  const s = d.schedule;
  if (!s.available) return <p className="card p-4 text-sm text-muted">{s.reason ?? "Give items a start date, a duration and optional dependencies to get a critical path."}</p>;
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3"><Stat label="Project duration" value={`${num(s.duration_days, 0)} d`} /><Stat label="Finish" value={s.finish ?? "—"} /><Stat label="Critical items" value={String(s.critical.length)} /></div>
      <Section title="Critical path method" note="Float is how long an item can slip without delaying the finish. Zero float = critical. Unknown dependencies are ignored, not guessed.">
        <Table caption="CPM schedule" head={["Item", "Start", "Finish", "Days", "ES", "EF", "LS", "LF", "Float", "Critical"]}
          rows={s.rows.map((r) => [r.title, r.start, r.finish, r.duration, r.es, r.ef, r.ls, r.lf, r.float, r.critical ? <Badge key="c" tone="bad">critical</Badge> : ""])} />
      </Section>
    </div>
  );
}

function Evm({ d }: { d: PmOverview }) {
  const e = d.earned_value;
  if (!e.available) return <p className="card p-4 text-sm text-muted">{e.reason ?? "Earned value needs planned cost, start date and duration on items."}</p>;
  const idx = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(2));
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="CPI" value={idx(e.cpi)} sub=">1 under budget" /><Stat label="SPI" value={idx(e.spi)} sub=">1 ahead of schedule" />
        <Stat label="EAC" value={usd(e.eac)} sub={`BAC ${usd(e.bac)}`} /><Stat label="VAC" value={usd(e.vac)} sub="BAC − EAC" />
        <Stat label="PV" value={usd(e.pv)} /><Stat label="EV" value={usd(e.ev)} /><Stat label="AC" value={usd(e.ac)} /><Stat label="TCPI" value={idx(e.tcpi)} sub="efficiency needed to hit BAC" />
      </div>
      <Section title="Reading" note={e.rule}><p className="text-sm">{e.reading}</p></Section>
    </div>
  );
}

function Risks({ d, act }: { d: PmOverview; act: Act }) {
  const r = d.risks;
  const [f, setF] = useState({ title: "", probability: "", impact_usd: "", owner: "", mitigation: "" });
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3"><Stat label="Open risks" value={String(r.open_count)} /><Stat label="Exposure (EMV)" value={usd(r.exposure)} sub="probability × impact, summed" /><Stat label="Reserve hint" value="" sub={r.reserve_hint} /></div>
      <div className="space-y-4">
        <Section title="Probability × impact matrix" note={r.matrix_note}>
          <table className="w-full max-w-sm text-center text-sm" aria-label="Risk matrix: rows are impact, high at the top; columns are probability, low on the left">
            <tbody>{[...r.matrix].reverse().map((row, i) => (
              <tr key={i}>{row.map((n, j) => {
                const sev = (2 - i) + j;   // reversed rows: top row = high probability
                return <td key={j} className={`border border-line p-3 ${n ? (sev >= 3 ? "bg-red-500/30" : sev === 2 ? "bg-amber-500/30" : "bg-emerald-500/20") : ""}`}>{n || ""}</td>;
              })}</tr>))}</tbody>
          </table>
          <p className="mt-1 text-xs text-muted">↑ impact · probability →</p>
        </Section>
        <Section title="Risk register">
          <Table head={["Risk", "P", "Impact", "EMV", "Status", "Mitigation", ""]}
            rows={r.risks.map((x) => [x.title, `${Math.round(x.probability * 100)}%`, usd(x.impact_usd), usd(x.emv), x.status, x.mitigation ?? "", <button key={x.id} className="btn !py-0.5 text-xs" onClick={() => act(() => deleteJson(`/api/pm/risks/${x.id}`))}>Delete</button>])} />
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <Field label="Risk"><input className="field" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
            <Field label="Probability (0–1)"><input className="field" inputMode="decimal" value={f.probability} onChange={(e) => setF({ ...f, probability: e.target.value })} /></Field>
            <Field label="Impact ($)"><input className="field" inputMode="decimal" value={f.impact_usd} onChange={(e) => setF({ ...f, impact_usd: e.target.value })} /></Field>
            <Field label="Owner"><input className="field" value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })} /></Field>
            <Field label="Mitigation"><input className="field" value={f.mitigation} onChange={(e) => setF({ ...f, mitigation: e.target.value })} /></Field>
          </div>
          <button className="btn btn-primary mt-3" disabled={!f.title || f.probability === ""} onClick={() => act(async () => { await postJson("/api/pm/risks", { ...f, status: "open" }); setF({ title: "", probability: "", impact_usd: "", owner: "", mitigation: "" }); })}>Add risk</button>
        </Section>
      </div>
    </div>
  );
}

function Okrs({ d, act }: { d: PmOverview; act: Act }) {
  const [f, setF] = useState({ objective: "", kr: "", start_value: "0", target_value: "", current_value: "0" });
  return (
    <div className="space-y-4">
      {d.okrs.objectives.map((o) => (
        <Section key={o.objective} title={`${o.objective} — ${num(o.progress_pct, 0)}%`}>
          <ul className="space-y-2">{o.key_results.map((k) => (
            <li key={k.id} className="text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2"><span>{k.kr}</span>
                <span className="flex items-center gap-2 text-xs text-muted">{k.current_value} / {k.target_value}
                  <button className="btn !py-0.5 text-xs" onClick={() => act(() => deleteJson(`/api/pm/okrs/${k.id}`))}>Delete</button></span></div>
              <div className="mt-1 h-2 rounded bg-panel2" role="progressbar" aria-valuenow={Math.round(k.progress_pct)} aria-valuemin={0} aria-valuemax={100} aria-label={k.kr}><div className="h-2 rounded bg-accent" style={{ width: `${Math.min(100, k.progress_pct)}%` }} /></div>
            </li>))}</ul>
        </Section>
      ))}
      {!d.okrs.objectives.length && <p className="card p-4 text-sm text-muted">No objectives yet.</p>}
      <Section title="Add a key result" note={d.okrs.note}>
        <div className="grid gap-2 sm:grid-cols-5">
          {(["objective", "kr", "start_value", "target_value", "current_value"] as const).map((k) => <Field key={k} label={k.replace("_", " ")}><input className="field" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></Field>)}
        </div>
        <button className="btn btn-primary mt-3" disabled={!f.objective || !f.kr || f.target_value === ""} onClick={() => act(async () => { await postJson("/api/pm/okrs", f); setF({ ...f, kr: "", target_value: "" }); })}>Add key result</button>
      </Section>
    </div>
  );
}

function Product() {
  const c = useChartColors();
  const [p, setP] = useState<PmProduct | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<PmProduct>("/api/pm/product-analytics").then(setP).catch((e) => setErr(errMsg(e, "Couldn't load product analytics."))); }, []);
  if (err) return <ErrorBanner message={err} />;
  if (!p) return <p className="text-sm text-muted">Loading…</p>;
  if (!p.available) return <p className="card p-4 text-sm text-muted">{p.reason ?? "No operations data in this workspace yet."}</p>;
  const maxCols = Math.max(0, ...(p.cohorts ?? []).map((x) => x.retention.length));
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted">{p.mapping}</p>
      <div className="grid gap-3 sm:grid-cols-3"><Stat label="Avg daily active" value={num(p.avg_dau)} /><Stat label="Monthly active" value={String(p.mau ?? 0)} /><Stat label="Stickiness (DAU÷MAU)" value={p.stickiness_pct == null ? "—" : `${p.stickiness_pct}%`} sub={p.stickiness_note} /></div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Weekly active accounts">
          <div className="h-52" role="img" aria-label="Line chart of weekly active accounts"><ResponsiveContainer width="100%" height="100%" minWidth={200}>
            <LineChart data={p.weekly_active}><CartesianGrid strokeDasharray="3 3" stroke={c.grid} /><XAxis dataKey="week" stroke={c.axis} fontSize={11} tickFormatter={(v: string) => v.slice(5)} /><YAxis stroke={c.axis} fontSize={11} width={32} allowDecimals={false} />
              <Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} /><Line dataKey="active" stroke={c.revenue} strokeWidth={2} dot={false} /></LineChart>
          </ResponsiveContainer></div>
        </Section>
        <Section title="Status funnel"><Table head={["Stage", "Records", "Share"]} rows={(p.funnel ?? []).map((x) => [x.stage, x.n, `${x.share_pct}%`])} /></Section>
      </div>
      <Section title="Monthly retention cohorts" note="Share of a cohort's accounts that were active again N months after their first record.">
        <Table head={["Cohort", "Size", ...Array.from({ length: maxCols }, (_, i) => `M${i}`)]}
          rows={(p.cohorts ?? []).map((x) => [x.cohort, x.size, ...Array.from({ length: maxCols }, (_, i) => (x.retention[i] == null ? "" : `${num(x.retention[i], 0)}%`))])} />
      </Section>
    </div>
  );
}
