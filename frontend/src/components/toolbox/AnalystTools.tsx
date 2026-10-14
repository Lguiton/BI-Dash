"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { API_BASE, deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Tabs, errMsg } from "@/components/panels/kit";
import { Notes, Pick, Rows, SourcePick, isDate, isNum, useCols } from "./common";

type Q = { sql: string; columns: string[]; rows: (string | number | null)[][]; notes: string[]; caution?: string };
type Pv = { row_labels: string[]; col_labels: string[]; matrix: (number | null)[][]; row_totals: (number | null)[]; col_totals: (number | null)[]; grand_total: number | null; notes: string[]; percent_of_total?: (number | null)[][] };
type Ab = { a: { rate: number; n: number }; b: { rate: number; n: number }; difference: number; relative_lift_pct: number | null; p_value: number; says?: string; caution?: string; confidence_interval?: number[] };
type Nb = { id: number; title: string; question: string; finding: string; created: string };

const METRICS = ["count", "sum", "avg", "median", "min", "max", "count_distinct", "ratio"].map((m) => ({ id: m, label: m.replace("_", " ") }));

function QuestionBuilder({ onSave }: { onSave: (q: Q, src: string, metric: string) => void }) {
  const [src, setSrc] = useState("");
  const cols = useCols(src);
  const [metric, setMetric] = useState("count");
  const [col, setCol] = useState("");
  const [den, setDen] = useState("");
  const [gb, setGb] = useState("");
  const [grain, setGrain] = useState("");
  const [order, setOrder] = useState("desc");
  const [res, setRes] = useState<Q | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const nums = cols.filter((c) => isNum(c.type)).map((c) => ({ id: c.name, label: c.name }));
  const all = cols.map((c) => ({ id: c.name, label: c.name }));
  const dates = cols.filter((c) => isDate(c.type)).map((c) => ({ id: c.name, label: c.name }));
  async function run() {
    setErr(null); setRes(null);
    try {
      setRes(await postJson<Q>("/api/toolbox/analyst/query", { source: src, metric, column: metric === "count" ? undefined : col || undefined, denominator: metric === "ratio" ? den || undefined : undefined, group_by: gb ? [gb] : [], grain: grain || undefined, order, limit: 50 }));
    } catch (e) { setErr(errMsg(e, "Could not run that question.")); }
  }
  return (
    <Section title="Question to answer" note="Pick from the lists. The tool writes the SQL for you, shows it, runs it read-only and warns about common mistakes like averaging a rate.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-3">
        <SourcePick value={src} onChange={(v) => { setSrc(v); setCol(""); setDen(""); setGb(""); setGrain(""); setRes(null); }} />
        <Pick label="What to calculate" value={metric} onChange={setMetric} options={METRICS} blank="" />
        {metric !== "count" && <Pick label={metric === "ratio" ? "Top column (add up)" : "Of this column"} value={col} onChange={setCol} options={metric === "count_distinct" || metric === "min" || metric === "max" ? all : nums} />}
        {metric === "ratio" && <Pick label="Bottom column (add up)" value={den} onChange={setDen} options={nums} />}
        <Pick label="Break down by" value={gb} onChange={setGb} options={all} blank="Nothing (one number)" />
        {dates.length > 0 && <Pick label="Group dates by" value={grain} onChange={setGrain} options={["day", "week", "month", "quarter", "year"].map((x) => ({ id: x, label: x }))} blank="Not by date" />}
        <Pick label="Order" value={order} onChange={setOrder} options={[{ id: "desc", label: "Biggest first" }, { id: "asc", label: "Smallest first" }]} blank="" />
      </div>
      <button className="btn mt-3" disabled={!src || (metric !== "count" && !col)} onClick={run}>Answer it</button>
      {res && (
        <div className="mt-3">
          <Notes items={res.notes} />
          <Rows columns={res.columns} rows={res.rows} caption="Answer" />
          <details className="mt-2 text-xs"><summary>Show the SQL</summary><pre className="mt-1 overflow-auto rounded bg-panel2 p-2">{res.sql}</pre></details>
          <button className="btn mt-2" onClick={() => onSave(res, src, metric)}>Save to notebook</button>
        </div>
      )}
    </Section>
  );
}

function PivotBuilder() {
  const [src, setSrc] = useState("");
  const cols = useCols(src);
  const [rows, setRows] = useState("");
  const [cc, setCc] = useState("");
  const [val, setVal] = useState("");
  const [agg, setAgg] = useState("sum");
  const [res, setRes] = useState<Pv | null>(null);
  const [pct, setPct] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const all = cols.map((c) => ({ id: c.name, label: c.name }));
  const nums = cols.filter((c) => isNum(c.type)).map((c) => ({ id: c.name, label: c.name }));
  async function run() {
    setErr(null); setRes(null);
    try { setRes(await postJson<Pv>("/api/toolbox/analyst/pivot", { source: src, rows, cols: cc || null, value: agg === "count" ? null : val || null, agg })); } catch (e) { setErr(errMsg(e, "Could not build the pivot.")); }
  }
  const m = res ? (pct && res.percent_of_total ? res.percent_of_total : res.matrix) : [];
  return (
    <Section title="Pivot builder" note="Rows by columns with totals and percent of total.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-3">
        <SourcePick value={src} onChange={(v) => { setSrc(v); setRows(""); setCc(""); setVal(""); setRes(null); }} />
        <Pick label="Rows" value={rows} onChange={setRows} options={all} />
        <Pick label="Columns (optional)" value={cc} onChange={setCc} options={all} blank="None" />
        <Pick label="How" value={agg} onChange={setAgg} options={[{ id: "sum", label: "Add up" }, { id: "avg", label: "Average" }, { id: "count", label: "Count rows" }]} blank="" />
        {agg !== "count" && <Pick label="Of this column" value={val} onChange={setVal} options={nums} />}
      </div>
      <button className="btn mt-3" disabled={!src || !rows || (agg !== "count" && !val)} onClick={run}>Build pivot</button>
      {res && (
        <div className="mt-3">
          <Notes items={res.notes} />
          <label className="mb-1 flex items-center gap-2 text-xs"><input type="checkbox" checked={pct} onChange={(e) => setPct(e.target.checked)} /> Show percent of total</label>
          <Rows columns={["", ...res.col_labels, "Total"]} rows={res.row_labels.map((r, i) => [r, ...(m[i] ?? []), res.row_totals[i]])} caption="Pivot" />
          <p className="mt-1 text-xs text-muted">Grand total {res.grand_total?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
        </div>
      )}
    </Section>
  );
}

function AbTools() {
  const [f, setF] = useState({ a_success: "", a_n: "", b_success: "", b_n: "" });
  const [r, setR] = useState<Ab | null>(null);
  const [sz, setSz] = useState({ base_rate: "", min_effect: "" });
  const [szr, setSzr] = useState<{ says: string } | null>(null);
  const [ma, setMa] = useState({ a: "", b: "" });
  const [mr, setMr] = useState<Ab | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const nums = (s: string) => s.split(/[\s,;]+/).filter(Boolean).map(Number);
  return (
    <Section title="A/B test and sample size" note="Textbook formulas you can check by hand. A p-value is not the chance the change is real.">
      {err && <ErrorBanner message={err} />}
      <h4 className="text-sm font-medium">Yes/no results (conversions)</h4>
      <div className="mt-1 grid gap-2 sm:grid-cols-4">
        {(["a_success", "a_n", "b_success", "b_n"] as const).map((k) => <Field key={k} label={({ a_success: "A: successes", a_n: "A: total", b_success: "B: successes", b_n: "B: total" })[k]}><input aria-label={k} className="input" inputMode="numeric" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></Field>)}
      </div>
      <button className="btn mt-2" onClick={async () => { setErr(null); try { setR(await postJson<Ab>("/api/toolbox/analyst/ab", { a_success: +f.a_success, a_n: +f.a_n, b_success: +f.b_success, b_n: +f.b_n })); } catch (e) { setErr(errMsg(e, "Check the numbers.")); } }}>Compare</button>
      {r && <p aria-label="AB result" className="mt-2 text-sm">{r.says ?? `p = ${r.p_value}`} <Badge tone={r.p_value < 0.05 ? "ok" : "muted"}>p {r.p_value}</Badge> {r.caution && <span className="text-xs text-muted">{r.caution}</span>}</p>}
      <h4 className="mt-4 text-sm font-medium">How many people do I need?</h4>
      <div className="mt-1 grid gap-2 sm:grid-cols-3">
        <Field label="Current rate (0.12 = 12%)"><input aria-label="base rate" className="input" value={sz.base_rate} onChange={(e) => setSz({ ...sz, base_rate: e.target.value })} /></Field>
        <Field label="Smallest lift worth finding (0.02 = 2 points)"><input aria-label="min effect" className="input" value={sz.min_effect} onChange={(e) => setSz({ ...sz, min_effect: e.target.value })} /></Field>
        <div className="self-end"><button className="btn" onClick={async () => { setErr(null); try { setSzr(await postJson("/api/toolbox/analyst/samplesize", { base_rate: +sz.base_rate, min_effect: +sz.min_effect })); } catch (e) { setErr(errMsg(e, "Check the numbers.")); } }}>Calculate</button></div>
      </div>
      {szr && <p className="mt-2 text-sm">{szr.says}</p>}
      <h4 className="mt-4 text-sm font-medium">Compare averages (numbers)</h4>
      <div className="mt-1 grid gap-2 sm:grid-cols-2">
        <Field label="Group A values (spaces or commas)"><textarea aria-label="group a" className="input" rows={2} value={ma.a} onChange={(e) => setMa({ ...ma, a: e.target.value })} /></Field>
        <Field label="Group B values"><textarea aria-label="group b" className="input" rows={2} value={ma.b} onChange={(e) => setMa({ ...ma, b: e.target.value })} /></Field>
      </div>
      <button className="btn mt-2" onClick={async () => { setErr(null); try { setMr(await postJson<Ab>("/api/toolbox/analyst/means", { a: nums(ma.a), b: nums(ma.b) })); } catch (e) { setErr(errMsg(e, "Need at least a few numbers in each group.")); } }}>Compare averages</button>
      {mr && <p className="mt-2 text-sm">{mr.says ?? `p = ${mr.p_value}`} <span className="text-xs text-muted">{mr.caution}</span></p>}
    </Section>
  );
}

function Survey() {
  const [src, setSrc] = useState("");
  const cols = useCols(src);
  const [col, setCol] = useState("");
  const [grp, setGrp] = useState("");
  const [res, setRes] = useState<{ says: string; options: Record<string, string | number>[]; caution?: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const all = cols.map((c) => ({ id: c.name, label: c.name }));
  return (
    <Section title="Survey analyzer" note="Each percentage comes with a range, because small groups swing.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-3">
        <SourcePick value={src} onChange={(v) => { setSrc(v); setCol(""); setGrp(""); setRes(null); }} />
        <Pick label="Question column" value={col} onChange={setCol} options={all} />
        <Pick label="Compare by (optional)" value={grp} onChange={setGrp} options={all} blank="Nobody" />
      </div>
      <button className="btn mt-3" disabled={!src || !col} onClick={async () => { setErr(null); setRes(null); try { setRes(await postJson("/api/toolbox/analyst/survey", { source: src, column: col, group: grp || null })); } catch (e) { setErr(errMsg(e, "Could not read that column.")); } }}>Analyze</button>
      {res && <div className="mt-3"><p className="text-sm">{res.says}</p><Rows columns={Object.keys(res.options[0] ?? {})} rows={res.options.map((o) => Object.values(o) as (string | number | null)[])} caption="Answers" />{res.caution && <p className="mt-1 text-xs text-muted">{res.caution}</p>}</div>}
    </Section>
  );
}

function Notebook({ draft, onClear, tick, bump }: { draft: { q: Q; src: string; metric: string } | null; onClear: () => void; tick: number; bump: () => void }) {
  const [list, setList] = useState<Nb[]>([]);
  const [f, setF] = useState({ title: "", question: "", finding: "", caveats: "" });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    getJson<{ entries: Nb[] }>("/api/toolbox/analyst/notebook").then((r) => { if (live) setList(r.entries); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load the notebook.")); });
    return () => { live = false; };
  }, [tick]);
  async function save() {
    setErr(null);
    try {
      await postJson("/api/toolbox/analyst/notebook", { ...f, sql: draft?.q.sql ?? "", result: draft ? { columns: draft.q.columns, rows: draft.q.rows } : null });
      setF({ title: "", question: "", finding: "", caveats: "" }); onClear(); bump();
    } catch (e) { setErr(errMsg(e, "Could not save.")); }
  }
  return (
    <Section title="Analysis notebook" note="Save a question, its answer and your finding as a write-up you can hand to a client.">
      {err && <ErrorBanner message={err} />}
      {draft && <p className="mb-2 text-xs"><Badge tone="ok">Result attached</Badge> from {draft.src} ({draft.metric})</p>}
      <div className="grid gap-2 sm:grid-cols-2">
        <Field label="Title"><input aria-label="Notebook title" className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="The question"><input aria-label="Notebook question" className="input" value={f.question} onChange={(e) => setF({ ...f, question: e.target.value })} /></Field>
        <Field label="What it means"><textarea aria-label="Notebook finding" className="input" rows={2} value={f.finding} onChange={(e) => setF({ ...f, finding: e.target.value })} /></Field>
        <Field label="Caveats"><textarea aria-label="Notebook caveats" className="input" rows={2} value={f.caveats} onChange={(e) => setF({ ...f, caveats: e.target.value })} /></Field>
      </div>
      <button className="btn mt-2" disabled={!f.title.trim()} onClick={save}>Save write-up</button>
      <ul className="mt-3 grid gap-1 text-sm">
        {list.map((n) => (
          <li key={n.id} className="flex flex-wrap items-center gap-2"><b>{n.title}</b> <span className="text-xs text-muted">{n.created}</span>
            <a className="btn" href={`${API_BASE}/api/toolbox/analyst/notebook/${n.id}/html`} target="_blank" rel="noreferrer">Open / print</a>
            <button className="btn" onClick={async () => { try { await deleteJson(`/api/toolbox/analyst/notebook/${n.id}`); bump(); } catch (e) { setErr(errMsg(e, "Could not delete.")); } }}>Delete</button></li>
        ))}
        {list.length === 0 && <li className="text-xs text-muted">No write-ups yet.</li>}
      </ul>
    </Section>
  );
}

export function AnalystTools() {
  const [tab, setTab] = useState("q");
  const [draft, setDraft] = useState<{ q: Q; src: string; metric: string } | null>(null);
  const [tick, setTick] = useState(0);
  return (
    <div className="grid gap-3">
      <Tabs label="Analyst tools" value={tab} onChange={setTab} tabs={[{ id: "q", label: "Question to answer" }, { id: "pv", label: "Pivot" }, { id: "ab", label: "A/B and sample size" }, { id: "sv", label: "Survey" }, { id: "nb", label: "Notebook" }]} />
      {tab === "q" && <QuestionBuilder onSave={(q, src, metric) => { setDraft({ q, src, metric }); setTab("nb"); }} />}
      {tab === "pv" && <PivotBuilder />}
      {tab === "ab" && <AbTools />}
      {tab === "sv" && <Survey />}
      {tab === "nb" && <Notebook draft={draft} onClear={() => setDraft(null)} tick={tick} bump={() => setTick((t) => t + 1)} />}
    </div>
  );
}
