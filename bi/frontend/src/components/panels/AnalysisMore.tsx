"use client";
import { useState } from "react";
import { CartesianGrid, ComposedChart, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis, Bar, Legend, Line } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Badge, Field, Section, Stat, Table, num } from "./kit";
import { ColSelect, Lesson, Sentences, Warn, first, groupish, pct, useRun, type Base, type Col } from "./analysisKit";

const GROUP_COLORS = ["var(--cat-1)", "var(--cat-2)", "var(--cat-3)", "var(--cat-4)", "var(--cat-5)", "var(--cat-6)", "var(--c-profit)", "var(--c-cost)"];

export function MultiPick({ legend, cols, value, onChange }: { legend: string; cols: Col[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <fieldset className="min-w-0 text-xs text-muted"><legend className="mb-1">{legend}</legend>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
        {cols.map((c) => <label key={c.name} className="flex items-center gap-1"><input type="checkbox" checked={value.includes(c.name)} onChange={() => onChange(value.includes(c.name) ? value.filter((x) => x !== c.name) : [...value, c.name])} />{c.name}</label>)}
      </div>
    </fieldset>
  );
}

// ---------------------------------------------------------------- business metrics (quantitative, past)
interface Biz { months: { month: string; revenue: number | null; cost: number | null; profit: number | null; margin_pct: number | null; growth_pct: number | null; net_burn: number | null; rows: number; active?: number; new?: number; lost?: number | null; churn_pct?: number | null }[]; headline: { latest_month: string; mrr: number | null; arr: number | null; growth_pct: number | null; margin_pct: number | null; avg_net_burn_3m: number | null; runway_months: number | null; cmgr_pct: number | null; avg_churn_pct: number | null; overall_margin_pct: number | null }; partial_last_month: boolean; sentences: string[]; notes: string[]; lesson: string }
export function BusinessTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const [date, setDate] = useState(first(cols, "date"));
  const [rev, setRev] = useState(nums.find((c) => /rev|sales|amount|income/i.test(c.name))?.name ?? nums[0]?.name ?? "");
  const [cost, setCost] = useState(nums.find((c) => /cost|expense|spend/i.test(c.name))?.name ?? "");
  const [ent, setEnt] = useState("");
  const [cash, setCash] = useState("");
  const r = useRun<Biz>();
  if (!cols.some((c) => c.kind === "date") || nums.length === 0) return <p className="text-sm text-muted">This needs a date column and a number column (revenue or sales).</p>;
  const h = r.data?.headline;
  const money = (v: number | null | undefined) => (v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 0 }));
  return (
    <div className="space-y-4">
      <Section title="Monthly business numbers" note="Gross margin, growth, burn, runway, MRR/ARR and customer churn, month by month, from your own data.">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <ColSelect label="Date column" value={date} onChange={setDate} cols={cols} kinds={["date"]} />
          <ColSelect label="Revenue column" value={rev} onChange={setRev} cols={cols} kinds={["number"]} />
          <ColSelect label="Cost column (optional)" value={cost} onChange={setCost} cols={cols} kinds={["number"]} none="None" />
          <ColSelect label="Customer column (optional, for churn)" value={ent} onChange={setEnt} cols={groupish(cols).length ? cols.filter((c) => c.kind !== "date") : cols} none="None" />
          <Field label="Cash on hand (optional, for runway)"><input className="field" inputMode="decimal" value={cash} onChange={(e) => setCash(e.target.value)} /></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !rev} onClick={() => r.run("/api/stats/business", { ...base, date_col: date, revenue_col: rev, cost_col: cost || null, entity_col: ent || null, cash: cash.trim() === "" ? null : Number(cash) })}>{r.busy ? "Working…" : "Calculate"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {r.data && h && (
        <>
          <Lesson text={r.data.lesson} />
          <Sentences items={r.data.sentences} />
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Stat label={`Revenue, ${h.latest_month}`} value={money(h.mrr)} sub="'MRR' (monthly revenue)" />
            <Stat label="ARR (×12)" value={money(h.arr)} />
            <Stat label="Growth, latest" value={h.growth_pct == null ? "—" : `${h.growth_pct}%`} sub={h.cmgr_pct == null ? undefined : `avg ${h.cmgr_pct}% / month`} />
            <Stat label="Margin, latest" value={h.margin_pct == null ? "n/a" : `${h.margin_pct}%`} sub={h.overall_margin_pct == null ? undefined : `overall ${h.overall_margin_pct}%`} />
            <Stat label="Net burn / month" value={h.avg_net_burn_3m == null ? "n/a" : money(h.avg_net_burn_3m)} sub={h.runway_months == null ? "enter cash for runway" : `${h.runway_months} months of runway`} />
            <Stat label="Avg churn" value={h.avg_churn_pct == null ? "n/a" : `${h.avg_churn_pct}%`} sub="customers not back next month" />
          </div>
          <div className="card h-72 min-w-0 p-3" role="img" aria-label="Monthly revenue and cost">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={r.data.months} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                <XAxis dataKey="month" stroke="var(--muted)" fontSize={11} />
                <YAxis stroke="var(--muted)" fontSize={11} width={56} tickFormatter={(x: number) => num(x, 0)} />
                <Tooltip /><Legend />
                <Bar dataKey="revenue" name="Revenue" fill="var(--c-revenue)" />
                {cost && <Bar dataKey="cost" name="Cost" fill="var(--c-cost)" />}
                {cost && <Line dataKey="profit" name="Profit" stroke="var(--c-profit)" strokeWidth={2} />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <Section title="Month by month">
            <Table head={["Month", "Revenue", "Cost", "Profit", "Margin", "Growth", "Net burn", ...(ent ? ["Active", "New", "Lost", "Churn"] : [])]}
              rows={r.data.months.map((m) => [m.month, money(m.revenue), money(m.cost), money(m.profit), m.margin_pct == null ? "—" : `${m.margin_pct}%`, m.growth_pct == null ? "—" : `${m.growth_pct}%`, money(m.net_burn),
                ...(ent ? [String(m.active ?? "—"), String(m.new ?? "—"), m.lost == null ? "—" : String(m.lost), m.churn_pct == null ? "—" : `${m.churn_pct}%`] : [])])} />
          </Section>
          <Warn items={r.data.notes} />
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- clusters
interface Clu { k: number; rows: number; silhouette: number; strength: string; k_scores: { k: number; silhouette: number }[]; groups: { id: number; size: number; pct: number; label: string; centroid: Record<string, number>; vs_average: Record<string, number> }[]; points: { x: number; y: number; g: number }[]; explained: number[]; warnings: string[]; sentences: string[]; lesson: string; features: string[] }
export function ClusterTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const [f, setF] = useState<string[]>(nums.slice(0, 2).map((c) => c.name));
  const [k, setK] = useState("");
  const r = useRun<Clu>();
  if (nums.length < 2) return <p className="text-sm text-muted">Clustering needs at least two number columns.</p>;
  const d = r.data;
  return (
    <div className="space-y-4">
      <Section title="Find natural groups" note="Data mining: group rows that look alike across several numbers, without telling it the groups in advance.">
        <MultiPick legend="Number columns to compare (2 to 8)" cols={nums} value={f} onChange={setF} />
        <div className="mt-2 max-w-xs"><Field label="Number of groups (blank = pick the best automatically)"><input className="field" type="number" min={2} max={10} value={k} onChange={(e) => setK(e.target.value)} /></Field></div>
        <button className="btn btn-primary mt-3" disabled={r.busy || f.length < 2} onClick={() => r.run("/api/stats/cluster", { ...base, features: f, k: k ? Number(k) : null })}>{r.busy ? "Working…" : "Find groups"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} /><Warn items={d.warnings} /><Sentences items={d.sentences} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Groups" value={String(d.k)} sub={d.k_scores.length ? "picked by best separation" : "chosen by you"} />
            <Stat label="Separation (silhouette)" value={num(d.silhouette, 2)} sub={d.strength} />
            <Stat label="Rows grouped" value={d.rows.toLocaleString()} />
          </div>
          <Section title="The groups on a map" note={`A flat view of the rows (the two directions that carry the most difference: ${pct(d.explained[0], 0)} and ${pct(d.explained[1], 0)}). Same color = same group.`}>
            <div className="h-72"><ResponsiveContainer width="100%" height="100%">
              <ComposedChart margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                <XAxis type="number" dataKey="x" stroke="var(--muted)" fontSize={11} hide /><YAxis type="number" dataKey="y" stroke="var(--muted)" fontSize={11} hide />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                {d.groups.map((g) => <Scatter key={g.id} name={`Group ${g.id}`} data={d.points.filter((p) => p.g === g.id)} fill={GROUP_COLORS[(g.id - 1) % GROUP_COLORS.length]} fillOpacity={0.7} />)}
                <Legend />
              </ComposedChart></ResponsiveContainer></div>
          </Section>
          <Section title="Who is in each group" note="'vs average' is how many standard deviations the group's average sits above (+) or below (−) everyone's. Give each group your own name.">
            <Table head={["Group", "Rows", "Looks like", ...d.features.map((x) => `${x} (avg)`), ...d.features.map((x) => `${x} vs average`)]}
              rows={d.groups.map((g) => [<b key="i">{g.id}</b>, `${g.size.toLocaleString()} (${g.pct}%)`, g.label, ...d.features.map((x) => num(g.centroid[x], 2)),
                ...d.features.map((x) => <span key={x} style={{ color: (g.vs_average[x] ?? 0) > 0.5 ? "var(--good)" : (g.vs_average[x] ?? 0) < -0.5 ? "var(--bad)" : undefined }}>{(g.vs_average[x] ?? 0) > 0 ? "+" : ""}{num(g.vs_average[x], 2)}</span>)])} />
          </Section>
          {d.k_scores.length > 0 && <p className="text-xs text-muted">Separation by number of groups: {d.k_scores.map((s) => `${s.k} → ${num(s.silhouette, 2)}`).join(", ")}.</p>}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- association rules
interface Assoc { baskets: number; items_total: number; multi_item_baskets: number; top_items: { item: string; baskets: number; pct: number }[]; rules: { if: string; then: string; baskets: number; support_pct: number; confidence_pct: number; lift: number }[]; warnings: string[]; sentences: string[]; lesson: string }
export function AssocTab({ base, cols }: { base: Base; cols: Col[] }) {
  const cats = cols.filter((c) => c.kind === "text" || c.kind === "bool");
  const grouping = cols.filter((c) => c.kind !== "date");
  const [basket, setBasket] = useState(cats.find((c) => /order|basket|customer|session|ticket/i.test(c.name))?.name ?? cats[0]?.name ?? "");
  const [item, setItem] = useState(cats.find((c) => /product|item|sku|category/i.test(c.name))?.name ?? cats[1]?.name ?? "");
  const [sup, setSup] = useState("1");
  const [conf, setConf] = useState("30");
  const r = useRun<Assoc>();
  if (cats.length < 2) return <p className="text-sm text-muted">This needs two category columns: one that groups rows into baskets (an order or a customer) and one that names the item.</p>;
  return (
    <div className="space-y-4">
      <Section title="What goes together?" note="Data mining: 'market basket' rules. The basket is what groups items (an order, a customer). Use a customer when each order holds one item.">
        <div className="grid gap-2 sm:grid-cols-4">
          <ColSelect label="Basket (what groups the items)" value={basket} onChange={setBasket} cols={grouping} />
          <ColSelect label="Item (what is in the basket)" value={item} onChange={setItem} cols={cats} />
          <Field label="Minimum support (% of baskets)"><input className="field" inputMode="decimal" value={sup} onChange={(e) => setSup(e.target.value)} /></Field>
          <Field label="Minimum confidence (%)"><input className="field" inputMode="decimal" value={conf} onChange={(e) => setConf(e.target.value)} /></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !basket || !item} onClick={() => r.run("/api/stats/associations", { ...base, basket_col: basket, item_col: item, min_support_pct: Number(sup) || 1, min_confidence_pct: Number(conf) || 0 })}>{r.busy ? "Working…" : "Find rules"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {r.data && (
        <>
          <Lesson text={r.data.lesson} /><Warn items={r.data.warnings} /><Sentences items={r.data.sentences} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Baskets" value={r.data.baskets.toLocaleString()} /><Stat label="Different items" value={r.data.items_total.toLocaleString()} /><Stat label="Baskets with 2+ items" value={r.data.multi_item_baskets.toLocaleString()} />
          </div>
          <Section title="Rules, strongest link first" note="Lift above 1 means they travel together more than chance. Confidence: of the baskets with the first item, the share that also have the second.">
            {r.data.rules.length === 0 ? <p className="text-sm text-muted">No pair passes these settings. Lower the minimum support.</p> :
              <Table head={["If the basket has", "it also has", "Baskets", "Support", "Confidence", "Lift"]} rows={r.data.rules.map((x) => [x.if, x.then, x.baskets.toLocaleString(), `${x.support_pct}%`, `${x.confidence_pct}%`, <b key="l">{x.lift}</b>])} />}
          </Section>
          <Section title="Most common items"><Table head={["Item", "Baskets", "Share"]} rows={r.data.top_items.map((x) => [x.item, x.baskets.toLocaleString(), `${x.pct}%`])} /></Section>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- outliers
interface Out { rows: number; flagged: number; features: string[]; outliers: { row: number; label: string | null; score: number; stranger_than_pct: number; values: Record<string, number>; most_unusual: string; z: number }[]; warnings: string[]; sentences: string[]; lesson: string }
export function OutlierTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const [f, setF] = useState<string[]>(nums.slice(0, 3).map((c) => c.name));
  const [label, setLabel] = useState("");
  const r = useRun<Out>();
  if (nums.length === 0) return <p className="text-sm text-muted">This needs number columns.</p>;
  return (
    <div className="space-y-4">
      <Section title="Find unusual rows" note="Data mining: rows that are odd across several columns together, including combinations a single-column check misses.">
        <MultiPick legend="Number columns to check" cols={nums} value={f} onChange={setF} />
        <div className="mt-2 max-w-xs"><ColSelect label="Show this to identify a row (optional)" value={label} onChange={setLabel} cols={cols} none="Row number only" /></div>
        <button className="btn btn-primary mt-3" disabled={r.busy || f.length === 0} onClick={() => r.run("/api/stats/outliers", { ...base, features: f, label_col: label || null })}>{r.busy ? "Working…" : "Find unusual rows"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {r.data && (
        <>
          <Lesson text={r.data.lesson} /><Warn items={r.data.warnings} /><Sentences items={r.data.sentences} />
          <Section title="Most unusual rows" note="'Stranger than' is the share of all rows that look more normal than this one.">
            <Table head={["Row", ...(label ? [label] : []), ...r.data.features, "Mainly because", "Stranger than"]}
              rows={r.data.outliers.map((o) => [`#${o.row}`, ...(label ? [o.label ?? "—"] : []), ...(r.data?.features ?? []).map((x) => num(o.values[x], 2)), `${o.most_unusual} (z ${o.z})`, <Badge key="s" tone="warn">{o.stranger_than_pct}%</Badge>])} />
          </Section>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- machine learning on any table
interface Ml { kind: string; model: string; model_label: string; target: string; train_rows: number; test_rows: number; metrics: Record<string, number | string | boolean | null>; confusion?: { labels: string[]; matrix: number[][] }; importance: { input: string; drop: number }[]; case?: { inputs: Record<string, string | number>; prediction: number | string; probabilities?: Record<string, number> | null; typical_miss?: number }; warnings: string[]; sentences: string[]; lesson: string }
export function MlTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const cats = cols.filter((c) => c.kind === "text" || c.kind === "bool");
  const targets = [...groupish(cols), ...nums];
  const [target, setTarget] = useState(targets[0]?.name ?? "");
  const [xn, setXn] = useState<string[]>(nums.filter((c) => c.name !== targets[0]?.name).slice(0, 3).map((c) => c.name));
  const [xc, setXc] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [pos, setPos] = useState("");
  const [vals, setVals] = useState<Record<string, string>>({});
  const r = useRun<Ml>();
  if (targets.length === 0 || nums.length === 0) return <p className="text-sm text-muted">This needs a column to predict and some number columns to learn from.</p>;
  const isNum = cols.find((c) => c.name === target)?.kind === "number";
  const opts = isNum ? [["linear", "Straight line (Ridge)"], ["forest", "Random forest"], ["boosting", "Gradient boosting"]] : [["logistic", "Straight line (logistic)"], ["forest", "Random forest"], ["boosting", "Gradient boosting"]];
  const useModel = opts.some(([id]) => id === model) ? model : opts[0][0];
  const xnUse = xn.filter((c) => c !== target);
  const caseReady = xnUse.length > 0 && xnUse.every((c) => (vals[c] ?? "") !== "");
  const go = () => r.run("/api/stats/predict", { ...base, target, x_numeric: xnUse, x_categorical: xc.filter((c) => c !== target), model: useModel, positive: pos || null, case: caseReady ? { ...vals, ...Object.fromEntries(xc.filter((c) => vals[c]).map((c) => [c, vals[c]])) } : null });
  const m = r.data?.metrics;
  return (
    <div className="space-y-4">
      <Section title="Teach a model to predict a column" note="Machine learning on any of your tables: it learns from most rows, then is graded on rows it never saw, against the simple guess.">
        <div className="grid gap-3 md:grid-cols-3">
          <ColSelect label="Column to predict" value={target} onChange={(v) => { setTarget(v); setModel(""); setPos(""); r.reset(); }} cols={targets} />
          <Field label="Method"><select className="field" value={useModel} onChange={(e) => setModel(e.target.value)}>{opts.map(([id, l]) => <option key={id} value={id}>{l}</option>)}</select></Field>
          {!isNum && <Field label="The outcome you care about (optional)"><input className="field" placeholder="e.g. yes" value={pos} onChange={(e) => setPos(e.target.value)} /></Field>}
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <MultiPick legend="Number inputs" cols={nums.filter((c) => c.name !== target)} value={xn} onChange={setXn} />
          <MultiPick legend="Category inputs (optional)" cols={cats.filter((c) => c.name !== target && (c.distinct ?? 2) <= 12)} value={xc} onChange={setXc} />
        </div>
        {xnUse.length > 0 && (
          <div className="mt-3"><p className="mb-1 text-xs text-muted">Try one case (optional): fill every number input to get a prediction.</p>
            <div className="grid gap-2 sm:grid-cols-4">{xnUse.map((c) => <Field key={c} label={c}><input className="field" inputMode="decimal" value={vals[c] ?? ""} onChange={(e) => setVals({ ...vals, [c]: e.target.value })} /></Field>)}</div></div>
        )}
        <button className="btn btn-primary mt-3" disabled={r.busy || (xnUse.length === 0 && xc.length === 0)} onClick={go}>{r.busy ? "Training…" : "Train and test"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {r.data && m && (
        <>
          <Lesson text={r.data.lesson} /><Warn items={r.data.warnings} /><Sentences items={r.data.sentences} />
          <div className="grid gap-3 sm:grid-cols-4">
            {r.data.kind === "regression" ? (<>
              <Stat label="Fit on new rows (R²)" value={pct(m.r2_test as number, 0)} sub={`on learned rows ${pct(m.r2_train as number, 0)}`} />
              <Stat label="Average miss" value={num(m.mae as number, 2)} sub={`guessing the average: ${num(m.baseline_mae as number, 2)}`} />
              <Stat label="Beats the simple guess?" value={m.better_than_baseline ? "Yes" : "No"} />
            </>) : (<>
              <Stat label="Right on new rows" value={pct(m.accuracy_test as number, 0)} sub={`always the common class: ${pct(m.baseline_accuracy as number, 0)}`} />
              <Stat label="Beats the simple guess?" value={m.better_than_baseline ? "Yes" : "No"} />
              {m.precision != null && <Stat label={`Of "${m.positive}" calls, right`} value={pct(m.precision as number, 0)} sub={`finds ${pct(m.recall as number, 0)} of all "${m.positive}"`} />}
              {m.auc != null && <Stat label="Ranking skill (AUC)" value={num(m.auc as number, 2)} sub="0.5 = coin flip, 1 = perfect" />}
            </>)}
            <Stat label="Learned from / tested on" value={`${r.data.train_rows.toLocaleString()} / ${r.data.test_rows.toLocaleString()}`} sub={r.data.model_label} />
          </div>
          {r.data.case && (
            <div className="card p-4 text-sm"><div className="text-xs uppercase tracking-wide text-muted">Prediction for your case</div>
              <div className="text-2xl font-bold tabular-nums">{typeof r.data.case.prediction === "number" ? num(r.data.case.prediction, 2) : r.data.case.prediction}</div>
              {r.data.case.probabilities && <div className="text-xs text-muted">{Object.entries(r.data.case.probabilities).map(([k, v]) => `${k}: ${pct(v, 0)}`).join(" · ")}</div>}
              {r.data.case.typical_miss != null && <div className="text-xs text-muted">Typical miss about ±{num(r.data.case.typical_miss, 2)}</div>}</div>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="What the model leaned on" note="How much the score drops when that input is shuffled. A guide to what mattered, not proof of cause.">
              <Table head={["Input", "Score drop"]} rows={r.data.importance.map((i) => [i.input, <div key="b" className="flex items-center gap-2"><div className="h-2 w-28 rounded bg-panel2"><div className="h-2 rounded" style={{ width: `${Math.max(0, Math.min(100, (i.drop / Math.max(r.data!.importance[0].drop, 1e-9)) * 100))}%`, background: "var(--accent)" }} /></div>{num(i.drop, 3)}</div>])} />
            </Section>
            {r.data.confusion && (
              <Section title="Right and wrong calls" note="Rows = what it really was, columns = what the model said. The diagonal is correct.">
                <Table head={["Really \\ Said", ...r.data.confusion.labels]} rows={r.data.confusion.matrix.map((row, i) => [<b key="l">{r.data!.confusion!.labels[i]}</b>, ...row.map((v) => v.toLocaleString())])} />
              </Section>
            )}
          </div>
        </>
      )}
    </div>
  );
}

