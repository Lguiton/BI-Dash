"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { Lesson, Warn } from "./analysisKit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TABS = [{ id: "dax", label: "DAX lab" }, { id: "fc", label: "Forecast methods" }, { id: "var", label: "Variance and scenarios" }, { id: "dist", label: "Distribution finder" }, { id: "doc", label: "Document reader" }];

function useCall<T = R>() {
  const [res, setRes] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = (path: string, body?: unknown, method: "post" | "get" = "post") => {
    setErr(null);
    (method === "get" ? getJson<T>(path) : postJson<T>(path, body)).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "That didn't work.")); });
  };
  return { res, err, run };
}
const Out = ({ c }: { c: { err: string | null } }) => (c.err ? <ErrorBanner message={c.err} /> : null);
const n = (v: unknown, d = 2) => (typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: d }) : v == null ? "—" : String(v));

export function BiToolkit() {
  const [tab, setTab] = useState("dax");
  return (
    <section className="card space-y-4 p-4" aria-label="BI toolkit">
      <h2 className="text-base font-semibold">BI toolkit: measures, forecasts, variance and documents</h2>
      <Lesson text="Practice versions of what BI work is made of. They run on a small built-in table or on data you paste, and they show their working. They teach the ideas; they are not Power BI, Fabric or an OCR engine." />
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="BI toolkit" />
      {tab === "dax" && <Dax />}
      {tab === "fc" && <Forecast />}
      {tab === "var" && <><Variance /><Scenario /></>}
      {tab === "dist" && <Dist />}
      {tab === "doc" && <Doc />}
    </section>
  );
}

function Dax() {
  const [f, setF] = useState("Total Sales = SUM(Sales[Amount])\nUSA Sales = CALCULATE([Total Sales], Sales[Country] = \"USA\")\nShare of USA = DIVIDE([USA Sales], [Total Sales])");
  const [g, setG] = useState("Country"); const [csv, setCsv] = useState("");
  const c = useCall(); const ref = useCall();
  useEffect(() => { ref.run("/api/bitools/dax/reference", undefined, "get"); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const go = () => {
    const measures = f.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => { const i = l.indexOf("="); return { name: l.slice(0, i).trim(), formula: l.slice(i + 1).trim() }; });
    c.run("/api/bitools/dax", { measures, group_by: g.split(",").map((s) => s.trim()).filter(Boolean), csv_text: csv.trim() || null });
  };
  const rows: R[] = c.res?.rows ?? [];
  return (
    <>
      <Section title="DAX measure lab" note="One measure per line as Name = formula. Columns are Table[Column], measures are [Name]. Built-in table: Sales (Date, Country, Category, Amount, Cost). Paste CSV below to use your own table, named Data.">
        <Field label="Measures"><textarea className="field font-mono" rows={5} value={f} onChange={(e) => setF(e.target.value)} aria-label="Measures" /></Field>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <Field label="Group by (up to 2 columns, comma separated)"><input className="field" value={g} onChange={(e) => setG(e.target.value)} /></Field>
          <Field label="Your own CSV (optional)"><textarea className="field font-mono" rows={2} value={csv} onChange={(e) => setCsv(e.target.value)} placeholder={"x,g\n1,a\n2,b"} /></Field>
        </div>
        <div className="mt-2"><button className="btn btn-primary" onClick={go}>Run measures</button></div>
        <Out c={c} />
        {c.res && <div className="mt-2 space-y-2">
          {rows.length > 0 && <Table head={Object.keys(rows[0])} rows={rows.map((r) => Object.values(r).map((v) => n(v)))} caption="Measure results" />}
          <Warn items={c.res.notes ?? []} />
          <p className="text-xs text-muted">{c.res.how}</p>
        </div>}
      </Section>
      {ref.res && <Section title="Examples, SQL equivalents and slips">
        <Table head={["Measure", "DAX", "Same idea in SQL"]} rows={(ref.res.examples as R[]).map((e) => [e.name, <code key="a">{e.dax}</code>, <code key="b">{e.sql}</code>])} caption="DAX examples" />
        <h4 className="mt-3 text-sm font-semibold">Not in this lab, and the SQL way</h4>
        <Table head={["Function", "Instead"]} rows={Object.entries(ref.res.unsupported as R).map(([k, v]) => [k, String(v)])} caption="Unsupported" />
        <h4 className="mt-3 text-sm font-semibold">Mistakes seen in teaching material</h4>
        <ul className="list-disc space-y-1 pl-5 text-sm">{(ref.res.slips as string[]).map((s) => <li key={s}>{s}</li>)}</ul>
        <p className="mt-2 text-xs text-muted">Not built: {(ref.res.not_built as string[]).join(" ")}</p>
      </Section>}
    </>
  );
}

function Forecast() {
  const [v, setV] = useState("20000, 22000, 24000, 26000, 28000, 30000, 32000, 34000, 36000, 38000");
  const [h, setH] = useState("3"); const [s, setS] = useState("0"); const c = useCall();
  const sample = () => getJson<{ values: number[] }>("/api/bitools/forecast/sample").then((r) => setV(r.values.join(", "))).catch(() => undefined);
  return (
    <Section title="Forecast method backtest" note="Hides the last few points, forecasts them with eight classical methods, and ranks the methods by how close they came. Use the winner for the next periods.">
      <Field label="History, oldest first (numbers separated by commas, spaces or lines)"><textarea className="field font-mono" rows={3} value={v} onChange={(e) => setV(e.target.value)} aria-label="History" /></Field>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        <Field label="Periods ahead"><input className="field" value={h} onChange={(e) => setH(e.target.value)} /></Field>
        <Field label="Season length (0 = none, 12 = monthly)"><input className="field" value={s} onChange={(e) => setS(e.target.value)} /></Field>
        <div className="flex items-end gap-2"><button className="btn btn-primary" onClick={() => c.run("/api/bitools/forecast", { values: v, horizon: Number(h) || 3, season: Number(s) || 0 })}>Compare methods</button><button className="btn" onClick={sample}>Use infographic sample</button></div>
      </div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3"><Stat label="Best method" value={c.res.best_label} /><Stat label="Test window" value={`${c.res.holdout} points`} /><Stat label="Forecast" value={(c.res.forecast as number[]).map((x) => n(x, 0)).join(", ")} /></div>
        <Table head={["Method", "MAE", "RMSE", "MAPE %", "Bias", "Beats naive"]} rows={(c.res.methods as R[]).map((m) => [m.label, n(m.mae), n(m.rmse), n(m.mape), n(m.bias), m.beats_naive ? <Badge key="y" tone="ok">yes</Badge> : <Badge key="n">no</Badge>])} caption="Methods ranked" />
        <Warn items={c.res.warnings as string[]} />
        <p className="text-xs text-muted">{Object.entries(c.res.metrics_help as R).map(([k, x]) => `${k}: ${x}`).join(". ")}.</p>
        <p className="text-xs text-muted">{c.res.limit}</p>
      </div>}
    </Section>
  );
}

function Variance() {
  const [t, setT] = useState("Sales, revenue, 100000, 112000\nCOGS, cost, 40000, 47000\nMarketing, cost, 12000, 9500\nRent, cost, 8000, 8000");
  const [thr, setThr] = useState("10"); const c = useCall();
  const go = () => c.run("/api/bitools/variance", { threshold_pct: Number(thr) || 10, rows: t.split("\n").map((l) => l.split(",").map((x) => x.trim())).filter((p) => p.length >= 4).map((p) => ({ item: p[0], kind: p[1], budget: Number(p[2]), actual: Number(p[3]) })) });
  return (
    <Section title="Budget vs actual variance" note="One line per row: item, revenue or cost, budget, actual. Above budget is good for revenue and bad for a cost; the table shows which.">
      <Field label="Lines"><textarea className="field font-mono" rows={5} value={t} onChange={(e) => setT(e.target.value)} aria-label="Variance lines" /></Field>
      <div className="mt-2 flex items-end gap-2"><Field label="Flag beyond %"><input className="field w-24" value={thr} onChange={(e) => setThr(e.target.value)} /></Field><button className="btn btn-primary" onClick={go}>Analyse</button></div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Stat label="Profit budget" value={n(c.res.profit.budget, 0)} /><Stat label="Profit actual" value={n(c.res.profit.actual, 0)} /><Stat label="Profit variance" value={n(c.res.profit.variance, 0)} /><Stat label="Margin actual" value={`${n(c.res.margin_pct.actual, 1)}%`} /></div>
        <Table head={["Item", "Kind", "Budget", "Actual", "Variance", "%", "Result"]} rows={(c.res.lines as R[]).map((l) => [l.item, l.kind, n(l.budget, 0), n(l.actual, 0), n(l.variance, 0), l.pct == null ? "—" : n(l.pct, 1), l.variance === 0 ? <Badge key="s">on budget</Badge> : <Badge key="f" tone={l.favourable ? "ok" : "bad"}>{l.favourable ? "favourable" : "unfavourable"}{l.flag ? " (flag)" : ""}</Badge>])} caption="Variance lines" />
        <ul className="list-disc pl-5 text-sm">{(c.res.summary as string[]).map((s) => <li key={s}>{s}</li>)}</ul>
        <Lesson text={c.res.lesson} />
        <p className="text-xs text-muted">{c.res.limit}</p>
      </div>}
    </Section>
  );
}

function Scenario() {
  const [p, setP] = useState({ price: "100", volume: "800", unit_cost: "60", fixed_cost: "20000" }); const c = useCall();
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setP({ ...p, [k]: e.target.value });
  return (
    <Section title="Scenario and sensitivity" note="Best, base and worst cases for a one-product profit model, plus which single driver moves profit the most.">
      <div className="grid gap-2 sm:grid-cols-4">
        {(["price", "volume", "unit_cost", "fixed_cost"] as const).map((k) => <Field key={k} label={k.replace("_", " ")}><input className="field" value={p[k]} onChange={set(k)} /></Field>)}
      </div>
      <div className="mt-2"><button className="btn btn-primary" onClick={() => c.run("/api/bitools/scenario", { price: Number(p.price), volume: Number(p.volume), unit_cost: Number(p.unit_cost), fixed_cost: Number(p.fixed_cost) })}>Run scenarios</button></div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Stat label="Base profit" value={n(c.res.base.profit, 0)} /><Stat label="Margin" value={`${n(c.res.base.margin_pct, 1)}%`} /><Stat label="Break-even units" value={n(c.res.break_even_units, 0)} /><Stat label="Biggest driver" value={c.res.sensitivity[0].driver} /></div>
        <Table head={["Scenario", "Price", "Volume", "Unit cost", "Revenue", "Profit", "Margin %"]} rows={(c.res.scenarios as R[]).map((s) => [s.name, n(s.price), n(s.volume, 0), n(s.unit_cost), n(s.revenue, 0), n(s.profit, 0), n(s.margin_pct, 1)])} caption="Scenarios" />
        <Table head={["Driver", `Profit if down ${c.res.sensitivity_step_pct}%`, `Profit if up ${c.res.sensitivity_step_pct}%`, "Swing"]} rows={(c.res.sensitivity as R[]).map((s) => [s.driver, n(s.profit_if_down, 0), n(s.profit_if_up, 0), n(s.swing, 0)])} caption="Sensitivity" />
        <Warn items={c.res.notes as string[]} />
        <Lesson text={c.res.lesson} />
        <p className="text-xs text-muted">{c.res.limit}</p>
      </div>}
    </Section>
  );
}

function Dist() {
  const [v, setV] = useState("12, 14, 15, 15, 16, 18, 19, 21, 22, 25, 31, 44, 58, 90");
  const [kind, setKind] = useState("normal"); const [a, setA] = useState("0"); const [b, setB] = useState("1"); const [x, setX] = useState("1.96");
  const fit = useCall(); const calc = useCall(); const ref = useCall();
  useEffect(() => { ref.run("/api/bitools/dist/reference", undefined, "get"); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const names: Record<string, [string, string]> = { normal: ["mean", "sd"], uniform: ["low", "high"], exponential: ["rate", ""], lognormal: ["mu", "sigma"], binomial: ["n", "p"], poisson: ["lam", ""] };
  const [k1, k2] = names[kind];
  const params: R = { [k1]: Number(a) }; if (k2) params[k2] = Number(b);
  return (
    <>
      <Section title="Which distribution does my data look like?" note="Checks skew, tails, bimodality and four goodness-of-fit tests, then tells you what that means for the statistics you can use.">
        <Field label="Values (commas, spaces or lines)"><textarea className="field font-mono" rows={3} value={v} onChange={(e) => setV(e.target.value)} aria-label="Values" /></Field>
        <div className="mt-2"><button className="btn btn-primary" onClick={() => fit.run("/api/bitools/dist/fit", { values: v })}>Find the shape</button></div>
        <Out c={fit} />
        {fit.res && <div className="mt-2 space-y-2">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Stat label="Shape" value={fit.res.shape} /><Stat label="Mean / median" value={`${n(fit.res.mean)} / ${n(fit.res.median)}`} /><Stat label="Skew" value={n(fit.res.skew)} /><Stat label="Excess kurtosis" value={n(fit.res.excess_kurtosis)} /></div>
          <Table head={["Candidate", "Fit", "Evidence"]} rows={(fit.res.candidates as R[]).map((cd) => [cd.name, <Badge key="f" tone={cd.fit === "good" ? "ok" : cd.fit === "poor" ? "bad" : "muted"}>{cd.fit}</Badge>, cd.evidence])} caption="Candidate distributions" />
          <ul className="list-disc space-y-1 pl-5 text-sm">{(fit.res.advice as string[]).map((s) => <li key={s}>{s}</li>)}</ul>
        </div>}
      </Section>
      <Section title="Probability calculator" note="Area under the curve: P(X ≤ x) and P(X > x).">
        <div className="grid gap-2 sm:grid-cols-5">
          <Field label="Distribution"><select className="field" value={kind} onChange={(e) => { setKind(e.target.value); setA("1"); setB("0.5"); }}>{Object.keys(names).map((k) => <option key={k}>{k}</option>)}</select></Field>
          <Field label={k1}><input className="field" value={a} onChange={(e) => setA(e.target.value)} /></Field>
          {k2 ? <Field label={k2}><input className="field" value={b} onChange={(e) => setB(e.target.value)} /></Field> : <div />}
          <Field label="x"><input className="field" value={x} onChange={(e) => setX(e.target.value)} /></Field>
          <div className="flex items-end"><button className="btn btn-primary" onClick={() => calc.run("/api/bitools/dist/calc", { kind, params, x: Number(x) })}>Calculate</button></div>
        </div>
        <Out c={calc} />
        {calc.res && <div className="mt-2 space-y-2">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Stat label="Probability ≤ x" value={n(calc.res.at?.cdf, 4)} /><Stat label="Probability > x" value={n(calc.res.at?.tail, 4)} /><Stat label="Mean" value={n(calc.res.facts?.mean, 3)} /><Stat label="Variance" value={n(calc.res.facts?.variance, 3)} /></div>
          <p className="text-sm">{calc.res.reading}</p>
        </div>}
      </Section>
      {ref.res && <Section title="Shapes at a glance">
        <Table head={["Shape", "Type", "Where you meet it"]} rows={(ref.res.shapes as R[]).map((s) => [s.name, s.type, s.note])} caption="Distribution shapes" />
        {Array.isArray(ref.res.slips) && <><h4 className="mt-3 text-sm font-semibold">Mistakes seen in teaching material</h4><ul className="list-disc space-y-1 pl-5 text-sm">{(ref.res.slips as string[]).map((s) => <li key={s}>{s}</li>)}</ul></>}
      </Section>}
    </>
  );
}

function Doc() {
  const [t, setT] = useState(""); const [kind, setKind] = useState("auto"); const c = useCall(); const info = useCall();
  useEffect(() => { info.run("/api/bitools/doc/info", undefined, "get"); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const samples: R = info.res?.samples ?? {};
  const dl = () => {
    const blob = new Blob([c.res?.csv ?? ""], { type: "text/csv" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "document.csv"; a.click(); URL.revokeObjectURL(a.href);
  };
  const fields: R = c.res?.fields ?? {};
  return (
    <Section title="Document reader: invoice, receipt or bank statement" note="Paste the text from any OCR tool or a copied PDF. This reads the fields and then does the checks a bookkeeper would: totals add up, balances roll forward, dates make sense. It does not read images.">
      <div className="flex flex-wrap gap-2">{Object.keys(samples).map((k) => <button key={k} className="btn" onClick={() => setT(samples[k])}>Load sample {k}</button>)}</div>
      <Field label="Document text"><textarea className="field mt-2 font-mono" rows={8} value={t} onChange={(e) => setT(e.target.value)} aria-label="Document text" /></Field>
      <div className="mt-2 flex items-end gap-2">
        <Field label="Type"><select className="field" value={kind} onChange={(e) => setKind(e.target.value)}>{["auto", "invoice", "receipt", "statement"].map((k) => <option key={k}>{k}</option>)}</select></Field>
        <button className="btn btn-primary" onClick={() => c.run("/api/bitools/doc", { text: t, kind, csv: true })}>Read document</button>
        {c.res?.csv && <button className="btn" onClick={dl}>Download CSV</button>}
      </div>
      <Out c={c} />
      {c.res && <div className="mt-2 space-y-2">
        <div className="flex gap-2"><Badge>{c.res.kind}</Badge>{c.res.needs_review ? <Badge tone="warn">needs review</Badge> : <Badge tone="ok">checks passed</Badge>}</div>
        <Table head={["Field", "Value"]} rows={Object.entries(fields).map(([k, x]) => [k, x == null ? "not found" : String(x)])} caption="Fields found" />
        {(c.res.checks as R[]).length > 0 && <Table head={["Check", "Result", "Working"]} rows={(c.res.checks as R[]).map((k) => [k.check, <Badge key="r" tone={k.ok ? "ok" : "bad"}>{k.ok ? "pass" : "fail"}</Badge>, k.detail])} caption="Checks" />}
        <Warn items={c.res.warnings as string[]} />
        {(c.res.rows as R[]).length > 0 && <Table head={Object.keys(c.res.rows[0])} rows={(c.res.rows as R[]).map((r) => Object.values(r).map((x) => (x == null ? "" : String(x))))} caption="Lines" />}
      </div>}
      {info.res && <div className="mt-3 text-xs text-muted"><p>Not built: {(info.res.not_built as string[]).join(" ")}</p><ul className="mt-1 list-disc pl-5">{(info.res.slips as string[]).map((s) => <li key={s}>{s}</li>)}</ul></div>}
    </Section>
  );
}
