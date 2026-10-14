"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { API_BASE, deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Tabs, errMsg } from "@/components/panels/kit";
import { HtmlFrame, Notes, Pick, fetchText } from "./common";

type Pack = { id: string; title: string };
type Sched = { id: number; pack: string; days: number; every_days: number; client: string; last_run: string | null; outputs: { date: string }[] };
type Rule = { id: number; pack: string; kpi: string; op: string; value: number; days: number };
type Alerts = { rules: Rule[]; triggered: { id: number; says: string; pack: string }[]; problems: { id: number; why: string }[]; note: string };
const DAYS = [7, 14, 30, 60, 90, 180, 365].map((d) => ({ id: String(d), label: `last ${d} days` }));

function usePacks(): Pack[] {
  const [p, setP] = useState<Pack[]>([]);
  useEffect(() => {
    let live = true;
    getJson<{ packs: (Pack & { rows: number | null })[] }>("/api/biz-packs").then((r) => { if (live) setP(r.packs.filter((x) => x.rows)); }).catch(() => {});
    return () => { live = false; };
  }, []);
  return p;
}
const po = (p: Pack[]) => p.map((x) => ({ id: x.id, label: x.title }));

function Designer({ mode }: { mode: "design" | "story" }) {
  const packs = usePacks();
  const [pack, setPack] = useState("");
  const [days, setDays] = useState("30");
  const [f, setF] = useState({ title: "", client: "", headline: "", recommendation: "" });
  const [html, setHtml] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function go() {
    setErr(null); setHtml(null);
    try { setHtml(await fetchText(`/api/toolbox/bi/${mode}`, { pack, days: +days, ...f })); } catch (e) { setErr(errMsg(e, "Could not build it.")); }
  }
  return (
    <Section title={mode === "design" ? "Dashboard designer" : "Data story"} note={mode === "design" ? "A clean one-page, client-ready report from a dashboard. Download it as HTML and print to PDF." : "A headline, the numbers that back it up, and one recommendation."}>
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-3">
        <Pick label="Dashboard" value={pack} onChange={setPack} options={po(packs)} />
        <Pick label="Period" value={days} onChange={setDays} options={DAYS} blank="" />
        <Field label="Client name"><input aria-label="Client name" className="input" value={f.client} onChange={(e) => setF({ ...f, client: e.target.value })} /></Field>
        {mode === "design" ? <Field label="Title"><input aria-label="Report title" className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field> : <>
          <Field label="Headline (what happened)"><input aria-label="Headline" className="input" value={f.headline} onChange={(e) => setF({ ...f, headline: e.target.value })} /></Field>
          <Field label="Recommendation"><input aria-label="Recommendation" className="input" value={f.recommendation} onChange={(e) => setF({ ...f, recommendation: e.target.value })} /></Field></>}
      </div>
      <button className="btn mt-3" disabled={!pack} onClick={go}>Build</button>
      {html && <HtmlFrame html={html} name={mode === "design" ? "client-report.html" : "data-story.html"} />}
    </Section>
  );
}

function Schedules() {
  const packs = usePacks();
  const [list, setList] = useState<Sched[]>([]);
  const [f, setF] = useState({ pack: "", days: "30", every: "30", client: "" });
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    getJson<{ items: Sched[] }>("/api/toolbox/bi/schedules").then((r) => { if (live) setList(r.items); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load.")); });
    return () => { live = false; };
  }, [tick]);
  const bump = () => setTick((t) => t + 1);
  return (
    <Section title="Scheduled client reports" note="A report that builds itself every N days. If your computer was off, it catches up the next time the app is running.">
      {err && <ErrorBanner message={err} />}{msg && <p className="mb-2 text-sm">{msg}</p>}
      <div className="grid gap-2 sm:grid-cols-4">
        <Pick label="Dashboard" value={f.pack} onChange={(v) => setF({ ...f, pack: v })} options={po(packs)} />
        <Pick label="Period" value={f.days} onChange={(v) => setF({ ...f, days: v })} options={DAYS} blank="" />
        <Field label="Every how many days"><input aria-label="Every days" className="input" inputMode="numeric" value={f.every} onChange={(e) => setF({ ...f, every: e.target.value })} /></Field>
        <Field label="Client name"><input aria-label="Schedule client" className="input" value={f.client} onChange={(e) => setF({ ...f, client: e.target.value })} /></Field>
      </div>
      <button className="btn mt-2" disabled={!f.pack} onClick={async () => { setErr(null); try { await postJson("/api/toolbox/bi/schedules", { pack: f.pack, days: +f.days, every_days: +f.every, client: f.client }); bump(); } catch (e) { setErr(errMsg(e, "Could not add.")); } }}>Add schedule</button>
      <ul className="mt-3 grid gap-2 text-sm">
        {list.map((s) => (
          <li key={s.id} className="flex flex-wrap items-center gap-2"><b>{s.pack}</b> every {s.every_days} days{s.client ? ` for ${s.client}` : ""} <span className="text-xs text-muted">last run {s.last_run ?? "never"}</span>
            <button className="btn" onClick={async () => { setErr(null); try { const r = await postJson<{ ran: number[]; skipped: { why: string }[] }>(`/api/toolbox/bi/schedules/${s.id}/run`, {}); setMsg(r.ran.length ? "Report built." : r.skipped[0]?.why ?? "Nothing built."); bump(); } catch (e) { setErr(errMsg(e, "Could not run.")); } }}>Run now</button>
            {s.outputs.slice(-3).reverse().map((o) => <a key={o.date} className="btn" href={`${API_BASE}/api/toolbox/bi/schedules/${s.id}/output/${o.date}`} target="_blank" rel="noreferrer">{o.date}</a>)}
            <button className="btn" onClick={async () => { try { await deleteJson(`/api/toolbox/bi/schedules/${s.id}`); bump(); } catch (e) { setErr(errMsg(e, "Could not remove.")); } }}>Remove</button></li>
        ))}
        {list.length === 0 && <li className="text-xs text-muted">No schedules yet.</li>}
      </ul>
    </Section>
  );
}

function AlertRules() {
  const packs = usePacks();
  const [data, setData] = useState<Alerts | null>(null);
  const [f, setF] = useState({ pack: "", kpi: "", op: "above", value: "" });
  const [kpis, setKpis] = useState<{ pack: string; labels: string[] }>({ pack: "", labels: [] });
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    getJson<Alerts>("/api/toolbox/bi/alerts").then((r) => { if (live) setData(r); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load.")); });
    return () => { live = false; };
  }, [tick]);
  useEffect(() => {
    if (!f.pack) return;
    let live = true;
    getJson<{ kpis: { label: string }[] }>(`/api/biz-packs/${f.pack}/dashboard?days=30`).then((r) => { if (live) setKpis({ pack: f.pack, labels: r.kpis.map((k) => k.label) }); }).catch(() => { if (live) setKpis({ pack: f.pack, labels: [] }); });
    return () => { live = false; };
  }, [f.pack]);
  const bump = () => setTick((t) => t + 1);
  const labels = kpis.pack === f.pack ? kpis.labels : [];
  return (
    <Section title="Alert rules" note="Checked when you open this page and on each scheduler pass. 'Worse by percent' compares with the previous period.">
      {err && <ErrorBanner message={err} />}
      {data && data.triggered.length > 0 && <ul aria-label="Triggered alerts" className="mb-3 grid gap-1">{data.triggered.map((t) => <li key={t.id} className="rounded border border-red-500 bg-red-500/10 p-2 text-sm">{t.says}</li>)}</ul>}
      {data && data.triggered.length === 0 && data.rules.length > 0 && <p className="mb-2 text-sm"><Badge tone="ok">All clear</Badge> No rule is tripped right now.</p>}
      <Notes items={data?.problems.map((p) => p.why)} />
      <div className="grid gap-2 sm:grid-cols-4">
        <Pick label="Dashboard" value={f.pack} onChange={(v) => setF({ ...f, pack: v, kpi: "" })} options={po(packs)} />
        <Pick label="KPI" value={f.kpi} onChange={(v) => setF({ ...f, kpi: v })} options={labels.map((l) => ({ id: l, label: l }))} />
        <Pick label="Alert me when it is" value={f.op} onChange={(v) => setF({ ...f, op: v })} options={[{ id: "above", label: "above" }, { id: "below", label: "below" }, { id: "worse_by_pct", label: "worse by % than before" }]} blank="" />
        <Field label="Value"><input aria-label="Alert value" className="input" inputMode="decimal" value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} /></Field>
      </div>
      <button className="btn mt-2" disabled={!f.pack || !f.kpi || f.value === ""} onClick={async () => { setErr(null); try { await postJson("/api/toolbox/bi/alerts", { pack: f.pack, kpi: f.kpi, op: f.op, value: +f.value }); bump(); } catch (e) { setErr(errMsg(e, "Could not add.")); } }}>Add rule</button>
      <ul className="mt-3 grid gap-1 text-sm">
        {data?.rules.map((r) => <li key={r.id} className="flex items-center gap-2">{r.pack}: {r.kpi} {r.op.replace(/_/g, " ")} {r.value}<button className="btn" onClick={async () => { try { await deleteJson(`/api/toolbox/bi/alerts/${r.id}`); bump(); } catch (e) { setErr(errMsg(e, "Could not remove.")); } }}>Remove</button></li>)}
      </ul>
    </Section>
  );
}

function Dictionary() {
  const [items, setItems] = useState<{ dashboard: string; kpi: string; unit: string; good_direction: string; in_words: string }[]>([]);
  useEffect(() => {
    let live = true;
    getJson<{ items: typeof items }>("/api/toolbox/bi/dictionary").then((r) => { if (live) setItems(r.items); }).catch(() => {});
    return () => { live = false; };
  }, []);
  return (
    <Section title="KPI dictionary" note="Every KPI in plain words and as a formula. Give it to a client so everyone means the same thing.">
      <div className="mb-2 flex gap-2"><a className="btn" href={`${API_BASE}/api/toolbox/bi/dictionary?fmt=csv`}>Download CSV</a><a className="btn" href={`${API_BASE}/api/toolbox/bi/dictionary?fmt=html`} target="_blank" rel="noreferrer">Open printable page</a></div>
      <ul className="grid max-h-96 gap-1 overflow-auto text-sm">{items.map((k, i) => <li key={i}><b>{k.kpi}</b> <span className="text-xs text-muted">{k.dashboard} · {k.good_direction} is good</span><br /><span className="text-xs">{k.in_words}</span></li>)}</ul>
    </Section>
  );
}

export function BiTools() {
  const [tab, setTab] = useState("design");
  return (
    <div className="grid gap-3">
      <Tabs label="BI tools" value={tab} onChange={setTab} tabs={[{ id: "design", label: "Dashboard designer" }, { id: "story", label: "Data story" }, { id: "sched", label: "Scheduled reports" }, { id: "alerts", label: "Alert rules" }, { id: "dict", label: "KPI dictionary" }]} />
      {tab === "design" && <Designer mode="design" />}
      {tab === "story" && <Designer mode="story" />}
      {tab === "sched" && <Schedules />}
      {tab === "alerts" && <AlertRules />}
      {tab === "dict" && <Dictionary />}
    </div>
  );
}
