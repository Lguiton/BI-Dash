"use client";
import { useCallback, useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson, putJson } from "@/lib/api";
import { useChartColors } from "@/lib/useChartColors";
import type { SaDictionary, SaOverview, SaProcess } from "@/lib/types";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg, num, useIsPractice } from "./kit";

const TABS = [
  { id: "req", label: "Requirements" }, { id: "dict", label: "Data dictionary" }, { id: "process", label: "Process analysis" },
  { id: "calc", label: "Calculators" }, { id: "feas", label: "Feasibility (TELOS)" },
];

export function SaPanel({ tab, onTab }: { tab: string; onTab: (t: string) => void }) {
  const [d, setD] = useState<SaOverview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const practice = useIsPractice();
  const [ver, setVer] = useState(0);
  const load = useCallback(async () => { setVer((v) => v + 1); }, []);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<SaOverview>("/api/sysanalyst", ctl.signal).then((r) => { setD(r); setErr(null); }).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load.")); });
    return () => ctl.abort();
  }, [ver]);
  const act = async (fn: () => Promise<unknown>) => { try { await fn(); await load(); } catch (e) { setErr(errMsg(e, "That didn't save.")); } };
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-center gap-2">
        <Tabs tabs={TABS} value={tab} onChange={onTab} label="Systems analysis views" />
        {d && d.requirements.length === 0 && practice && <button className="btn" onClick={() => act(() => postJson("/api/sysanalyst/requirements/example", {}))}>Load example requirements</button>}
      </div>
      {tab === "req" && (d ? <Requirements d={d} act={act} /> : <p className="text-sm text-muted">Loading…</p>)}
      {tab === "dict" && <Dictionary />}
      {tab === "process" && <Process />}
      {tab === "calc" && <Calculators />}
      {tab === "feas" && (d ? <Feasibility d={d} act={act} /> : <p className="text-sm text-muted">Loading…</p>)}
    </div>
  );
}
type Act = (fn: () => Promise<unknown>) => Promise<void>;

function Requirements({ d, act }: { d: SaOverview; act: Act }) {
  const t = d.traceability;
  const [f, setF] = useState({ code: "", title: "", kind: "functional", priority: "must", status: "proposed", source: "", acceptance: "", test_ref: "" });
  const set = (k: string) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Requirements" value={String(t.total)} sub={Object.entries(t.by_status).filter(([, n]) => n).map(([k, n]) => `${n} ${k}`).join(" · ")} />
        <Stat label="Test coverage" value={t.test_coverage_pct == null ? "—" : `${t.test_coverage_pct}%`} sub="built or tested items with a test reference" />
        <Stat label="Traceability gaps" value={String(t.gaps.length)} />
      </div>
      {t.gaps.length > 0 && <Section title="Gaps" note={t.note}><ul className="list-disc space-y-1 pl-5 text-sm">{t.gaps.map((g) => <li key={g.code + g.problem}><b>{g.code}</b> {g.title}: {g.problem}</li>)}</ul></Section>}
      <Section title="Requirements register">
        <Table caption="Requirements" head={["Code", "Requirement", "Type", "Priority", "Status", "Acceptance", "Test", ""]}
          rows={d.requirements.map((r) => [r.code, r.title, r.kind, r.priority, <select key="s" aria-label={`Status of ${r.code}`} className="field !py-0.5 text-xs" value={r.status} onChange={(e) => act(() => putJson(`/api/sysanalyst/requirements/${r.id}`, { ...r, status: e.target.value }))}>{d.enums.status.map((s) => <option key={s}>{s}</option>)}</select>,
            r.acceptance ?? "", r.test_ref ?? "", <button key="d" className="btn !py-0.5 text-xs" onClick={() => act(() => deleteJson(`/api/sysanalyst/requirements/${r.id}`))}>Delete</button>])} />
      </Section>
      <Section title="Add a requirement" note="Write each as a testable statement. 'The system shall…' plus an acceptance criterion someone could check.">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Code (e.g. FR-1)"><input className="field" value={f.code} onChange={set("code")} /></Field>
          <Field label="Requirement"><input className="field" value={f.title} onChange={set("title")} /></Field>
          <Field label="Type"><select className="field" value={f.kind} onChange={set("kind")}>{d.enums.kinds.map((k) => <option key={k}>{k}</option>)}</select></Field>
          <Field label="Priority (MoSCoW)"><select className="field" value={f.priority} onChange={set("priority")}>{d.enums.priority.map((k) => <option key={k}>{k}</option>)}</select></Field>
          <Field label="Source / stakeholder"><input className="field" value={f.source} onChange={set("source")} /></Field>
          <Field label="Acceptance criterion"><input className="field" value={f.acceptance} onChange={set("acceptance")} /></Field>
          <Field label="Test reference"><input className="field" value={f.test_ref} onChange={set("test_ref")} /></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={!f.code || !f.title} onClick={() => act(async () => { await postJson("/api/sysanalyst/requirements", f); setF({ ...f, code: "", title: "", acceptance: "", test_ref: "" }); })}>Add requirement</button>
      </Section>
    </div>
  );
}

function Dictionary() {
  const [d, setD] = useState<SaDictionary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => { getJson<SaDictionary>("/api/sysanalyst/dictionary").then(setD).catch((e) => setErr(errMsg(e, "Couldn't load."))); }, []);
  if (err) return <ErrorBanner message={err} />;
  if (!d) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-4">
      {d.tables.map((t) => (
        <Section key={t.name} title={`${t.name} (${t.kind}, ${t.rows.toLocaleString()} rows)`} note={t.description}>
          <Table caption={`Columns of ${t.name}`} head={["Column", "Type", "Key", "Nulls", "Distinct", "Meaning"]}
            rows={t.columns.map((c) => [c.name, c.type, c.key, c.null_pct == null ? "—" : `${c.null_pct}%`, c.distinct ?? "—", c.description])} />
        </Section>
      ))}
      <Section title="Relationships" note="Orphans are child rows whose parent key doesn't exist (a referential-integrity problem).">
        <Table head={["From", "To", "Meaning", "Orphans"]} rows={d.relationships.map((r) => [`${r.from_table}.${r.from_column}`, `${r.to_table}.${r.to_column}`, r.meaning, r.orphans ? <Badge key="o" tone="bad">{r.orphans}</Badge> : <Badge key="o" tone="ok">0</Badge>])} />
      </Section>
      <Section title="ER diagram (Mermaid)" note="Paste into mermaid.live or a Markdown file on GitHub to render it.">
        <button className="btn mb-2" onClick={() => { void navigator.clipboard?.writeText(d.mermaid).then(() => setCopied(true)); }}>{copied ? "Copied" : "Copy Mermaid"}</button>
        <pre className="max-h-72 overflow-auto rounded-md bg-panel2 p-3 text-xs" tabIndex={0}><code>{d.mermaid}</code></pre>
      </Section>
    </div>
  );
}

function Process() {
  const [p, setP] = useState<SaProcess | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<SaProcess>("/api/sysanalyst/process").then(setP).catch((e) => setErr(errMsg(e, "Couldn't load."))); }, []);
  if (err) return <ErrorBanner message={err} />;
  if (!p) return <p className="text-sm text-muted">Loading…</p>;
  if (!p.available || !p.duration) return <p className="card p-4 text-sm text-muted">{p.reason ?? "Process analysis needs records with a duration."}</p>;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Median duration" value={`${num(p.duration.p50)} min`} sub={`p85 ${num(p.duration.p85)} · p95 ${num(p.duration.p95)}`} />
        <Stat label="Variability (CV)" value={num(p.duration.cv, 2)} sub={p.variability} />
        <Stat label="Bottleneck" value={p.bottleneck?.entity ?? "—"} sub={p.bottleneck?.why} />
        <Stat label="Avg in progress" value={num(p.littles_law?.avg_in_progress, 2)} sub={p.littles_law?.reading} />
      </div>
      <Section title="By entity (slowest first)">
        <Table caption="Process by entity" head={["Entity", "Records", "Avg min", "p85 min", "Units/hour", "Cost/unit", "Completed"]}
          rows={(p.entities ?? []).map((e) => [e.entity, e.records, num(e.avg_min), num(e.p85_min), num(e.units_per_hour), e.cost_per_unit == null ? "—" : `$${num(e.cost_per_unit, 2)}`, e.completion_pct == null ? "—" : `${e.completion_pct}%`])} />
      </Section>
    </div>
  );
}

function Num({ label, v, set }: { label: string; v: string; set: (s: string) => void }) {
  return <Field label={label}><input className="field" inputMode="decimal" value={v} onChange={(e) => set(e.target.value)} /></Field>;
}
type R = Record<string, unknown>;
function Result({ r }: { r: R | null }) {
  if (!r) return null;
  return <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">{Object.entries(r).filter(([, v]) => typeof v !== "object" || v === null).map(([k, v]) => (
    <div key={k} className={`flex justify-between gap-3 border-b border-line py-1 ${typeof v === "string" && v.length > 24 ? "sm:col-span-2" : ""}`}><dt className="text-muted">{k.replace(/_/g, " ")}</dt><dd className="text-right tabular-nums">{typeof v === "number" ? num(v, 3) : String(v ?? "—")}</dd></div>))}</dl>;
}
function Calculators() {
  const c = useChartColors();
  const [q, setQ] = useState({ arrival_rate: "5", service_rate: "6", servers: "1", target_wait: "" });
  const [a, setA] = useState({ slo: "99.9", window_days: "30", used_minutes: "0", parts: "", mode: "serial" });
  const [cb, setCb] = useState({ initial: "10000", annual_benefit: "5000", annual_cost: "500", years: "5", rate: "10" });
  const [cp, setCp] = useState({ load: "100", capacity: "200", growth: "5", headroom: "80" });
  const [out, setOut] = useState<Record<string, R | null>>({});
  const [err, setErr] = useState<string | null>(null);
  const run = async (key: string, path: string, params: Record<string, string>) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "")).toString();
    try { setOut((o) => ({ ...o, [key]: null })); const r = await getJson<R>(`/api/sysanalyst/calc/${path}?${qs}`); setOut((o) => ({ ...o, [key]: r })); setErr(null); }
    catch (e) { setErr(errMsg(e, "Calculation failed.")); }
  };
  const proj = (out.cap?.projection as { month: number; load: number }[] | undefined) ?? [];
  const flows = (out.cb?.cashflows as { year: number; cumulative_discounted: number }[] | undefined) ?? [];
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Queueing (M/M/1 and M/M/c)" note="Rates share one time unit, e.g. per hour. Utilisation near 100% makes waits explode; this is why systems feel fine, then suddenly don't.">
          <div className="grid gap-2 sm:grid-cols-4"><Num label="Arrivals / unit" v={q.arrival_rate} set={(s) => setQ({ ...q, arrival_rate: s })} /><Num label="Service rate / server" v={q.service_rate} set={(s) => setQ({ ...q, service_rate: s })} /><Num label="Servers" v={q.servers} set={(s) => setQ({ ...q, servers: s })} /><Num label="Target wait" v={q.target_wait} set={(s) => setQ({ ...q, target_wait: s })} /></div>
          <button className="btn btn-primary mt-3" onClick={() => run("q", "queue", q)}>Calculate</button><Result r={out.q ?? null} />
        </Section>
        <Section title="Availability and error budget" note="Parts: comma-separated availabilities (%) to combine in serial (all needed) or parallel (any one is enough).">
          <div className="grid gap-2 sm:grid-cols-3"><Num label="SLO %" v={a.slo} set={(s) => setA({ ...a, slo: s })} /><Num label="Window (days)" v={a.window_days} set={(s) => setA({ ...a, window_days: s })} /><Num label="Downtime used (min)" v={a.used_minutes} set={(s) => setA({ ...a, used_minutes: s })} />
            <Field label="Parts (%)"><input className="field" value={a.parts} onChange={(e) => setA({ ...a, parts: e.target.value })} placeholder="99.9, 99.5" /></Field>
            <Field label="Mode"><select className="field" value={a.mode} onChange={(e) => setA({ ...a, mode: e.target.value })}><option>serial</option><option>parallel</option></select></Field></div>
          <button className="btn btn-primary mt-3" onClick={() => run("a", "availability", a)}>Calculate</button><Result r={out.a ?? null} />
        </Section>
        <Section title="Cost-benefit">
          <div className="grid gap-2 sm:grid-cols-5"><Num label="Upfront $" v={cb.initial} set={(s) => setCb({ ...cb, initial: s })} /><Num label="Benefit / yr" v={cb.annual_benefit} set={(s) => setCb({ ...cb, annual_benefit: s })} /><Num label="Cost / yr" v={cb.annual_cost} set={(s) => setCb({ ...cb, annual_cost: s })} /><Num label="Years" v={cb.years} set={(s) => setCb({ ...cb, years: s })} /><Num label="Discount %" v={cb.rate} set={(s) => setCb({ ...cb, rate: s })} /></div>
          <button className="btn btn-primary mt-3" onClick={() => run("cb", "cost-benefit", cb)}>Calculate</button><Result r={out.cb ?? null} />
          {flows.length > 0 && <div className="mt-3 h-40" role="img" aria-label="Cumulative discounted cash flow by year"><ResponsiveContainer width="100%" height="100%" minWidth={200}><LineChart data={flows}><CartesianGrid strokeDasharray="3 3" stroke={c.grid} /><XAxis dataKey="year" stroke={c.axis} fontSize={11} /><YAxis stroke={c.axis} fontSize={11} width={48} /><Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} /><Line dataKey="cumulative_discounted" stroke={c.profit} strokeWidth={2} dot /></LineChart></ResponsiveContainer></div>}
        </Section>
        <Section title="Capacity planning">
          <div className="grid gap-2 sm:grid-cols-4"><Num label="Current load" v={cp.load} set={(s) => setCp({ ...cp, load: s })} /><Num label="Capacity" v={cp.capacity} set={(s) => setCp({ ...cp, capacity: s })} /><Num label="Growth % / month" v={cp.growth} set={(s) => setCp({ ...cp, growth: s })} /><Num label="Headroom limit %" v={cp.headroom} set={(s) => setCp({ ...cp, headroom: s })} /></div>
          <button className="btn btn-primary mt-3" onClick={() => run("cap", "capacity", cp)}>Calculate</button><Result r={out.cap ?? null} />
          {proj.length > 0 && <div className="mt-3 h-40" role="img" aria-label="Projected load by month"><ResponsiveContainer width="100%" height="100%" minWidth={200}><LineChart data={proj}><CartesianGrid strokeDasharray="3 3" stroke={c.grid} /><XAxis dataKey="month" stroke={c.axis} fontSize={11} /><YAxis stroke={c.axis} fontSize={11} width={40} /><Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} /><Line dataKey="load" stroke={c.revenue} strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div>}
        </Section>
      </div>
    </div>
  );
}

function Feasibility({ d, act }: { d: SaOverview; act: Act }) {
  const [v, setV] = useState<Record<string, { score: string; weight: string; note: string }>>(
    Object.fromEntries(d.feasibility.rows.map((r) => [r.key, { score: r.score == null ? "" : String(r.score), weight: String(r.weight), note: r.note }])));
  const f = d.feasibility;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3"><Stat label="Weighted score" value={f.weighted_score == null ? "—" : `${f.weighted_score} / 5`} /><Stat label="Verdict" value={f.verdict ?? "Not scored"} /><Stat label="Weakest area" value={f.weakest ?? "—"} /></div>
      <Section title="TELOS feasibility" note={f.scale ?? "Score each 1 (very weak) to 5 (very strong). A single score below 3 caps the verdict, whatever the average."}>
        <div className="space-y-3">{f.rows.map((r) => (
          <div key={r.key} className="grid gap-2 sm:grid-cols-[1fr_5rem_5rem_1fr] sm:items-end">
            <div className="text-sm"><b>{r.label}</b><div className="text-xs text-muted">{r.question}</div></div>
            <Field label="Score 1–5"><input className="field" inputMode="decimal" value={v[r.key]?.score ?? ""} onChange={(e) => setV({ ...v, [r.key]: { ...v[r.key], score: e.target.value } })} /></Field>
            <Field label="Weight"><input className="field" inputMode="decimal" value={v[r.key]?.weight ?? "1"} onChange={(e) => setV({ ...v, [r.key]: { ...v[r.key], weight: e.target.value } })} /></Field>
            <Field label="Evidence"><input className="field" value={v[r.key]?.note ?? ""} onChange={(e) => setV({ ...v, [r.key]: { ...v[r.key], note: e.target.value } })} /></Field>
          </div>))}</div>
        <button className="btn btn-primary mt-3" onClick={() => act(() => putJson("/api/sysanalyst/feasibility", Object.fromEntries(Object.entries(v).map(([k, x]) => [k, { score: x.score, weight: x.weight || 1, note: x.note }]))))}>Save scores</button>
      </Section>
    </div>
  );
}
