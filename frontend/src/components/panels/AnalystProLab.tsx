"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Section, Table, Tabs, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
type Fld = { k: string; label: string; area?: boolean };
type Tool = { label: string; path: string; fields: Fld[]; def: Record<string, string>; help: string };
const TOOLS: Record<string, Tool> = {
  forecast: { label: "Forecast with a range", path: "forecast", fields: [{ k: "values", label: "Numbers, oldest first (one per month, week or day)", area: true }, { k: "season", label: "Season length (12 monthly, 7 daily, 4 quarterly)" }, { k: "horizon", label: "Periods ahead" }, { k: "width", label: "Range width (typical errors)" }], def: { values: "58 58 60 53 48 68 74 86 93 99 93 82 74 65 79 55 63 87 91 95 112 120 111 95 89 84 91 79 73 97 101 111 128 140 137 111", season: "12", horizon: "3", width: "2" }, help: "Same period last cycle, scaled by growth, with a range from how wrong it was on recent periods." },
  cohort: { label: "Cohorts and retention", path: "cohort", fields: [{ k: "text", label: "Lines of: customer id, date (or leave empty and use a table below)", area: true }, { k: "table", label: "Table name (optional)" }, { k: "id_col", label: "Customer column" }, { k: "date_col", label: "Date column" }], def: { text: "a,2026-01-05\na,2026-02-01\nb,2026-01-10\nc,2026-02-03\nc,2026-03-02\nd,2026-02-14", table: "", id_col: "", date_col: "" }, help: "Who comes back, by the month they first appeared." },
  funnel: { label: "Funnel", path: "funnel", fields: [{ k: "text", label: "Lines of: step, count", area: true }], def: { text: "Visited,1000\nSigned up,300\nTrial started,180\nPaid,60" }, help: "Where people drop out, and the biggest leak." },
  pareto: { label: "Pareto (80/20)", path: "calc/pareto", fields: [{ k: "text", label: "Lines of: category, value", area: true }], def: { text: "Late delivery,42\nWrong item,25\nDamaged,12\nBilling error,8\nOther,5" }, help: "Which few causes make most of the problem." },
  ab: { label: "A/B test", path: "calc/ab", fields: [{ k: "a_visitors", label: "A visitors" }, { k: "a_conversions", label: "A conversions" }, { k: "b_visitors", label: "B visitors" }, { k: "b_conversions", label: "B conversions" }], def: { a_visitors: "1000", a_conversions: "100", b_visitors: "1000", b_conversions: "130" }, help: "Is the difference real or chance?" },
  breakeven: { label: "Break-even", path: "calc/breakeven", fields: [{ k: "fixed_costs", label: "Fixed costs" }, { k: "price", label: "Price per unit" }, { k: "variable_cost", label: "Variable cost per unit" }, { k: "target_profit", label: "Target profit (optional)" }], def: { fixed_costs: "5000", price: "25", variable_cost: "10", target_profit: "0" }, help: "How many sales to cover costs." },
  unit: { label: "Unit economics", path: "calc/unit", fields: [{ k: "monthly_revenue_per_customer", label: "Monthly revenue per customer" }, { k: "gross_margin_pct", label: "Gross margin %" }, { k: "monthly_churn_pct", label: "Monthly churn %" }, { k: "cac", label: "Cost to win a customer" }], def: { monthly_revenue_per_customer: "50", gross_margin_pct: "80", monthly_churn_pct: "5", cac: "200" }, help: "Lifetime value, payback and LTV to cost." },
  margin: { label: "Margins", path: "calc/margin", fields: [{ k: "revenue", label: "Revenue" }, { k: "cogs", label: "Cost of goods" }, { k: "operating_costs", label: "Operating costs" }], def: { revenue: "1000", cogs: "600", operating_costs: "250" }, help: "Gross, operating margin and markup." },
  runway: { label: "Cash runway", path: "calc/runway", fields: [{ k: "cash", label: "Cash on hand" }, { k: "monthly_costs", label: "Monthly costs" }, { k: "monthly_income", label: "Monthly income" }], def: { cash: "30000", monthly_costs: "10000", monthly_income: "4000" }, help: "How many months the cash lasts." },
  cycle: { label: "Cash cycle", path: "calc/cycle", fields: [{ k: "receivables", label: "Receivables" }, { k: "revenue", label: "Revenue (year)" }, { k: "inventory", label: "Inventory" }, { k: "cogs", label: "Cost of goods (year)" }, { k: "payables", label: "Payables" }], def: { receivables: "30000", revenue: "365000", inventory: "20000", cogs: "200000", payables: "10000" }, help: "Days to turn spending back into cash." },
  npv: { label: "NPV and IRR", path: "calc/npv", fields: [{ k: "rate", label: "Discount rate %" }, { k: "cashflows", label: "Cash flows, first is the cost (negative)" }], def: { rate: "10", cashflows: "-10000, 3000, 4000, 5000" }, help: "Is an investment worth it?" },
  star: { label: "Star schema", path: "calc/star", fields: [{ k: "columns", label: "Columns of your flat table, comma separated", area: true }, { k: "grain", label: "Grain: one row per ..." }], def: { columns: "order_id, customer_id, order_date, product_name, category, amount, quantity, region", grain: "one row per order line" }, help: "Split a flat table into a fact and dimensions." },
  review: { label: "Dashboard review", path: "calc/review", fields: [{ k: "text", label: "Describe the dashboard: charts, numbers, colors, axes, reader", area: true }], def: { text: "14 KPI tiles, a pie chart with 12 slices, a dual-axis line chart, 3D bars and rainbow colors for the reader to scroll." }, help: "Catches common design mistakes." },
  metric: { label: "Metric definition", path: "calc/metric", fields: [{ k: "name", label: "Metric name" }, { k: "formula", label: "Definition" }, { k: "owner", label: "Owner" }, { k: "source", label: "Source system and table" }, { k: "grain", label: "Grain and refresh" }, { k: "caveats", label: "Caveats" }], def: { name: "Active customers", formula: "Distinct customers with a paid order in the month", owner: "", source: "", grain: "", caveats: "" }, help: "One agreed definition per metric." },
  requirements: { label: "Requirements", path: "calc/requirements", fields: [{ k: "role", label: "Who you are talking to (executive, manager, finance, operations)" }, { k: "audience", label: "Audience" }, { k: "decisions", label: "Decisions it supports" }, { k: "metrics", label: "Key metrics" }, { k: "refresh", label: "Refresh" }], def: { role: "manager", audience: "", decisions: "", metrics: "", refresh: "daily" }, help: "Interview questions and a requirements page." },
};
const TABS = [...Object.entries(TOOLS).map(([id, t]) => ({ id, label: t.label })), { id: "recipes", label: "Window functions" }, { id: "dax", label: "SQL, DAX, Tableau, Excel" }, { id: "qa", label: "Report QA and rollout" }];
const skip = new Set(["note", "caveats", "caveat", "tips", "rules", "good_practice", "how_to_read", "watch", "how_range_works", "questions", "document", "text", "sql", "charts", "findings", "message"]);
const arr = (a: unknown) => (Array.isArray(a) ? a : []) as any[];
const cell = (v: any) => (Array.isArray(v) ? v.join(" · ") : v !== null && typeof v === "object" ? JSON.stringify(v) : String(v ?? ""));

function Result({ out }: { out: R }) {
  const scalars = Object.entries(out).filter(([k, v]) => !skip.has(k) && (["number", "string", "boolean"].includes(typeof v)));
  const tables = Object.entries(out).filter(([k, v]) => !skip.has(k) && Array.isArray(v) && v.length > 0 && typeof v[0] === "object");
  const lists = ["findings_text", "tips", "rules", "watch", "caveats", "good_practice", "questions"].filter((k) => arr(out[k]).length > 0 && typeof arr(out[k])[0] === "string");
  return (
    <div className="mt-3 space-y-2 text-sm" role="status">
      {out.verdict && <p><strong>{out.verdict}</strong></p>}
      {out.message && <p><strong>{out.message}</strong></p>}
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">{scalars.filter(([k]) => k !== "verdict").map(([k, v]) => <div key={k} className="contents"><dt className="text-muted">{k.replace(/_/g, " ")}</dt><dd>{String(v)}</dd></div>)}</dl>
      {tables.map(([k, v]) => { const rows = v as any[]; const heads = Object.keys(rows[0]); return <Table key={k} caption={k.replace(/_/g, " ")} head={heads.map((h) => h.replace(/_/g, " "))} rows={rows.slice(0, 40).map((r) => heads.map((h) => cell(r[h])))} />; })}
      {arr(out.findings).length > 0 && <ul className="space-y-1">{arr(out.findings).map((x, i) => <li key={i} className="rounded border border-line p-2"><strong>{x.problem}</strong><div className="text-xs">{x.fix}</div></li>)}</ul>}
      {out.findings && arr(out.findings).length === 0 && <p className="text-muted">No common mistakes found in that description.</p>}
      {typeof out.sql === "string" && <pre className="overflow-auto rounded bg-panel2 p-2 text-xs">{out.sql}</pre>}
      {typeof out.document === "string" && <pre className="whitespace-pre-wrap rounded bg-panel2 p-2 font-sans text-xs">{out.document}</pre>}
      {typeof out.text === "string" && <pre className="whitespace-pre-wrap rounded bg-panel2 p-2 font-sans text-xs">{out.text}</pre>}
      {arr(out.charts).length > 0 && <Table caption="Pick the chart by the question" head={["Question", "Use", "Avoid"]} rows={arr(out.charts).map((c) => [c.question, c.use, c.avoid])} />}
      {lists.map((k) => <div key={k}><div className="text-xs font-semibold capitalize">{k.replace(/_/g, " ")}</div><ul className="list-disc pl-5 text-xs">{arr(out[k]).map((x, i) => <li key={i}>{x}</li>)}</ul></div>)}
      {(out.how_to_read || out.how_range_works) && <p className="text-xs">{out.how_to_read ?? out.how_range_works}</p>}
      {(out.note || out.caveat) && <p className="text-xs text-muted">{out.note} {out.caveat}</p>}
    </div>
  );
}

/** Advanced analyst tools: forecast with a range, cohorts, funnels, finance maths, A/B test, star schema, window-function recipes, DAX and Tableau map, design review, metric definitions and report QA. Local only. */
export function AnalystProLab() {
  const [tab, setTab] = useState("forecast");
  const [f, setF] = useState<Record<string, string>>({});
  const [out, setOut] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [rec, setRec] = useState<R | null>(null);
  const [ran, setRan] = useState<R | null>(null);
  const [dax, setDax] = useState<R | null>(null);
  const [ref, setRef] = useState<R | null>(null);
  const t = TOOLS[tab];
  const val = (k: string) => f[`${tab}.${k}`] ?? t?.def[k] ?? "";
  useEffect(() => {
    const bad = (e: unknown) => setErr(errMsg(e, "Couldn't load that."));
    if (tab === "recipes" && !rec) getJson<R>("/api/analystpro/recipes").then(setRec).catch(bad);
    if (tab === "dax" && !dax) getJson<R>("/api/analystpro/dax").then(setDax).catch(bad);
    if (tab === "qa" && !ref) getJson<R>("/api/analystpro/reference").then(setRef).catch(bad);
  }, [tab, rec, dax, ref]);
  async function go() {
    if (!t) return;
    setErr(null);
    const body: R = {};
    t.fields.forEach((x) => { body[x.k] = val(x.k); });
    try { setOut(await postJson<R>(`/api/analystpro/${t.path}`, body)); } catch (e) { setOut(null); setErr(errMsg(e, "Check what you entered.")); }
  }
  async function runRecipe(id: string) { setErr(null); try { setRan(await getJson<R>(`/api/analystpro/recipes/${id}`)); } catch (e) { setErr(errMsg(e, "Couldn't run that.")); } }
  return (
    <section className="card space-y-3 p-4" aria-label="Advanced analyst lab">
      <h2 className="text-base font-semibold">Advanced analysis: forecasts, cohorts, finance, SQL window functions, DAX and report quality</h2>
      <p className="text-xs text-muted">Everything runs on this computer from what you paste. Results are estimates to check against your data.</p>
      <Tabs tabs={TABS} value={tab} onChange={(v) => { setTab(v); setOut(null); setErr(null); }} label="Analyst tools" />
      {err && <ErrorBanner message={err} />}
      {t && (
        <Section title={t.label} note={t.help}>
          <div className="grid gap-2 sm:grid-cols-2">
            {t.fields.map((x) => (
              <label key={x.k} className={`text-xs ${x.area ? "sm:col-span-2" : ""}`}>{x.label}
                {x.area ? <textarea className="input mt-1 w-full font-mono" rows={4} value={val(x.k)} onChange={(e) => setF((s) => ({ ...s, [`${tab}.${x.k}`]: e.target.value }))} />
                  : <input className="input mt-1 w-full" value={val(x.k)} onChange={(e) => setF((s) => ({ ...s, [`${tab}.${x.k}`]: e.target.value }))} />}
              </label>
            ))}
          </div>
          <button className="btn mt-2" onClick={go}>Calculate</button>
          {out && <Result out={out} />}
        </Section>
      )}
      {tab === "recipes" && rec && (
        <Section title="Window function recipes" note={`Run each on ${rec.sample_table}. Your data is not touched.`}>
          <ul className="space-y-2 text-sm">
            {arr(rec.recipes).map((r) => (
              <li key={r.id} className="rounded border border-line p-2">
                <div className="flex flex-wrap items-center gap-2"><strong>{r.title}</strong><button className="btn" onClick={() => runRecipe(r.id)}>Run it</button></div>
                <div className="text-xs text-muted">{r.idea}</div>
                <pre className="mt-1 overflow-auto rounded bg-panel2 p-2 text-xs">{r.sql}</pre>
                {ran && ran.id === r.id && <Table caption="Result" head={ran.columns} rows={arr(ran.rows).map((row) => row.map(cell))} />}
              </li>
            ))}
          </ul>
        </Section>
      )}
      {tab === "dax" && dax && (
        <Section title="Same idea in SQL, Power BI, Tableau and Excel" note={dax.note}>
          <Table head={dax.columns} rows={arr(dax.rows).map((r) => r.map((x: string) => <code key={x} className="text-xs">{x}</code>))} />
          <ul className="mt-2 list-disc pl-5 text-xs">{arr(dax.tips).map((x, i) => <li key={i}>{x}</li>)}</ul>
        </Section>
      )}
      {tab === "qa" && ref && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Section title="Report QA checklist"><ul className="list-disc pl-5 text-xs">{arr(ref.qa).map((x, i) => <li key={i}>{x}</li>)}</ul></Section>
          <Section title="Self-service rollout"><ul className="list-disc pl-5 text-xs">{arr(ref.rollout).map((x, i) => <li key={i}>{x}</li>)}</ul></Section>
        </div>
      )}
    </section>
  );
}
