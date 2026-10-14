"use client";
import Link from "next/link";
import { CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Badge, Field, Section, Stat, Table, num } from "./kit";
import { MultiPick } from "./AnalysisMore";
import { ColSelect, Lesson, Sentences, Warn, first, groupish, useRun, type Base, type Col } from "./analysisKit";

// ---------------------------------------------------------------- guide: the mining techniques and where they live
const TECHNIQUES: { n: string; d: string; ex: string; tab: string }[] = [
  { n: "Pattern recognition", d: "Finding regularities in data, such as the hour most users log in.", ex: "Trends and patterns, Clusters", tab: "Descriptive and Predictive tabs" },
  { n: "Trend", d: "The general tendency of data to change over time, beyond year-to-year wobble.", ex: "Trends and patterns (trend line, seasonality)", tab: "Descriptive" },
  { n: "Classification", d: "Sort rows into target categories, such as low, medium or high spenders.", ex: "Machine learning, Decision tree", tab: "Predictive" },
  { n: "Clustering", d: "Group similar rows so each group can be treated alike.", ex: "Clusters", tab: "Predictive" },
  { n: "Anomaly or outlier detection", d: "Find unusual values, such as a spike in card use that may be misuse.", ex: "Outliers", tab: "Diagnostic" },
  { n: "Association rules", d: "Events that tend to happen together, such as laptop and cooling pad.", ex: "Bought together", tab: "Predictive" },
  { n: "Sequential patterns", d: "Events in order, such as a shopping trail from login to logout.", ex: "Sequences", tab: "Predictive" },
  { n: "Affinity grouping", d: "Co-occurrence used to recommend what others with the same item also bought.", ex: "Bought together (lift shows how strong)", tab: "Predictive" },
  { n: "Decision trees", d: "A tree of yes/no branches that you can read from input to output.", ex: "Decision tree", tab: "Predictive" },
  { n: "Regression", d: "The nature of the relationship between variables, causal or only correlational.", ex: "Regression, Correlation", tab: "Diagnostic and Predictive" },
];
const MINING_TOOLS: { n: string; d: string; status: string; tone: "ok" | "muted" | "bad" }[] = [
  { n: "Spreadsheets (Excel, Google Sheets, LibreOffice Calc)", d: "Pivot tables to sort and compare big sets of data; add-ins such as XLMiner add classification, regression, association rules and clustering.", status: "LibreOffice Calc pivot tables (see BI tool categories); mining itself is built in here", tone: "muted" },
  { n: "R and RStudio", d: "Hundreds of packages for regression, classification, clustering, association rules, text mining, outliers and social networks (tm, twitteR).", status: "Skipped: R by your choice", tone: "bad" },
  { n: "Python: pandas, NumPy, Jupyter", d: "pandas for loading, organizing and summarizing data (mean, median, mode, range, correlation); NumPy for maths; Jupyter notebooks for exploring step by step.", status: "Python lab; scikit-learn powers the mining tabs here", tone: "ok" },
  { n: "IBM SPSS Statistics", d: "Closed-source, licensed, low-code package for advanced and text analytics and trend analysis.", status: "Skipped: licensed software", tone: "bad" },
  { n: "IBM Watson Studio", d: "Cloud or desktop workspace built on Jupyter and open-source tools, plus SPSS Modeler flows, for team projects and ML models.", status: "Skipped: cloud add-on", tone: "bad" },
  { n: "SAS Enterprise Miner", d: "Graphical mining workbench for exploring relationships and anomalies, big data, and validating findings.", status: "Skipped: SAS by your choice", tone: "bad" },
];
export function MiningGuideTab() {
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Data mining extracts knowledge from data using pattern recognition, statistics and mathematics. Its goals are to find correlations, patterns and variations, understand trends, and predict probabilities. Statistics supplies the measures, and helps tell random noise from a significant finding. Common uses: targeted campaigns, fraud flags, risk and treatment priorities, student support, demand forecasts.</p>
      <Table head={["Technique", "What it does", "Where to find it here"]} rows={TECHNIQUES.map((t) => [<b key="n">{t.n}</b>, t.d, <span key="w">{t.ex} <Badge>{t.tab}</Badge></span>])} />
      <Section title="Tools for data mining">
        <ul className="space-y-2 text-sm">{MINING_TOOLS.map((t) => <li key={t.n}><b>{t.n}.</b> {t.d} <Badge tone={t.tone}>{t.status}</Badge></li>)}</ul>
      </Section>
      <p className="text-xs text-muted">Mining finds leads, not proof. Test a promising pattern on new data before acting on it. For the statistics behind it see Distribution, Compare groups and Correlation, or the <Link href="/ml" className="underline">ML Lab</Link> for hands-on practice.</p>
    </div>
  );
}

// ---------------------------------------------------------------- decision tree
interface TNode { condition: string; n: number; prediction: string | number; confidence?: number; shares?: Record<string, number>; children?: TNode[] }
interface Tree {
  kind: string; rows_used: number; leaves: number; tree: TNode; sentences: string[]; warnings: string[]; lesson: string;
  metrics: { accuracy_test?: number; baseline_accuracy?: number; sensitivity?: number; specificity?: number; false_positives?: number; false_negatives?: number; focus_class?: string; auc?: number; p_vs_baseline?: number; mae?: number; baseline_mae?: number; r2_test?: number; better_than_baseline: boolean };
  importance: { input: string; weight: number }[];
  roc?: { fpr: number; tpr: number }[] | null;
  cost_sweep?: { cost: number; sensitivity: number; specificity: number; accuracy: number; false_positives: number; false_negatives: number }[] | null;
}
function TreeNode({ n, depth }: { n: TNode; depth: number }) {
  const leaf = !n.children;
  return (
    <li className="space-y-1">
      <div className={`rounded border border-line p-2 text-sm ${leaf ? "bg-panel2" : ""}`}>
        <b>{n.condition}</b> <span className="text-muted">({n.n.toLocaleString()} rows)</span>
        {leaf && <> {"→"} guess <b>{String(n.prediction)}</b>{n.confidence != null && <span className="text-muted"> ({Math.round(n.confidence * 100)}% of these rows)</span>}</>}
      </div>
      {n.children && <ul className="ml-4 space-y-1 border-l border-line pl-3">{n.children.map((c, i) => <TreeNode key={`${depth}-${i}`} n={c} depth={depth + 1} />)}</ul>}
    </li>
  );
}
export function TreeTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const targets = [...groupish(cols), ...nums];
  const [target, setTarget] = useState(targets[0]?.name ?? "");
  const [xn, setXn] = useState<string[]>(nums.filter((c) => c.name !== targets[0]?.name).slice(0, 3).map((c) => c.name));
  const [xc, setXc] = useState<string[]>([]);
  const [depth, setDepth] = useState(3);
  const [focus, setFocus] = useState("");
  const [cost, setCost] = useState(1);
  const r = useRun<Tree>();
  if (targets.length === 0 || nums.length === 0) return <p className="text-sm text-muted">A decision tree needs a column to predict and some number columns to learn from.</p>;
  const d = r.data;
  const cats = groupish(cols).filter((c) => c.name !== target);
  return (
    <div className="space-y-4">
      <Section title="Build a decision tree">
        <div className="grid gap-2 sm:grid-cols-2">
          <ColSelect label="Column to predict" value={target} onChange={(v) => { setTarget(v); setXn(xn.filter((x) => x !== v)); setXc(xc.filter((x) => x !== v)); }} cols={targets} />
          <Field label="Outcome you most want to catch (optional)"><input className="field" placeholder="e.g. yes (default: the rarer one)" maxLength={120} value={focus} onChange={(e) => setFocus(e.target.value)} /></Field>
          <Field label="Cost of missing it, compared with a false alarm"><select className="field" value={cost} onChange={(e) => setCost(Number(e.target.value))}>{[1, 2, 4, 9].map((n) => <option key={n} value={n}>{n} to 1{n === 1 ? " (equal, the default)" : ""}</option>)}</select></Field>
          <Field label="How deep (questions in a row)"><select className="field" value={depth} onChange={(e) => setDepth(Number(e.target.value))}>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}{n === 3 ? " (good start)" : ""}</option>)}</select></Field>
        </div>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <MultiPick legend="Number inputs" cols={nums.filter((c) => c.name !== target)} value={xn} onChange={setXn} />
          <MultiPick legend="Category inputs (optional)" cols={cats} value={xc} onChange={setXc} />
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || (xn.length + xc.length === 0)} onClick={() => r.run("/api/stats/tree", { ...base, target, x_numeric: xn, x_categorical: xc, max_depth: depth, focus_class: focus || undefined, focus_cost: cost })}>{r.busy ? "Growing…" : "Build the tree"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} /><Sentences items={d.sentences} /><Warn items={d.warnings} />
          <div className="grid gap-3 sm:grid-cols-3">
            {d.kind === "classification"
              ? <><Stat label="Right on new rows" value={`${Math.round((d.metrics.accuracy_test ?? 0) * 100)}%`} sub={`simple guess ${Math.round((d.metrics.baseline_accuracy ?? 0) * 100)}%`} /><Stat label="Rows used" value={d.rows_used.toLocaleString()} /></>
              : <><Stat label="Average miss" value={num(d.metrics.mae, 3)} sub={`simple guess ${num(d.metrics.baseline_mae, 3)}`} /><Stat label="R² on new rows" value={num(d.metrics.r2_test, 2)} /></>}
            <Stat label="End boxes (leaves)" value={String(d.leaves)} />
          </div>
          {d.kind === "classification" && d.metrics.sensitivity != null && (
            <Section title={`Catching '${d.metrics.focus_class}': hits and false alarms`} note="Sensitivity is the share of real cases caught. Specificity is the share of the others correctly left alone. Overall accuracy can look good while sensitivity is poor.">
              <div className="grid gap-3 sm:grid-cols-4">
                <Stat label="Sensitivity" value={`${Math.round((d.metrics.sensitivity ?? 0) * 100)}%`} />
                <Stat label="Specificity" value={`${Math.round((d.metrics.specificity ?? 0) * 100)}%`} />
                <Stat label="Missed (false negatives)" value={String(d.metrics.false_negatives ?? 0)} />
                <Stat label="False alarms (false positives)" value={String(d.metrics.false_positives ?? 0)} />
              </div>
              {d.cost_sweep && <Table head={["Cost of a miss", "Sensitivity", "Specificity", "Overall accuracy", "Missed", "False alarms"]} rows={d.cost_sweep.map((x) => [`${x.cost} to 1`, `${Math.round(x.sensitivity * 100)}%`, `${Math.round(x.specificity * 100)}%`, `${Math.round(x.accuracy * 100)}%`, String(x.false_negatives), String(x.false_positives)])} caption="Same tree, different relative cost of a miss" />}
              {d.roc && d.cost_sweep && (
                <div className="mt-3">
                  <div className="card h-72 min-w-0 p-3" role="img" aria-label="ROC curve: true positive rate against false positive rate, with the chance line and the four cost settings">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart margin={{ top: 8, right: 12, bottom: 18, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                        <XAxis dataKey="x" type="number" domain={[0, 1]} stroke="var(--muted)" fontSize={11} label={{ value: "False positive rate (false alarms)", position: "insideBottom", offset: -8, fontSize: 11 }} />
                        <YAxis type="number" domain={[0, 1]} stroke="var(--muted)" fontSize={11} width={40} label={{ value: "Sensitivity", angle: -90, position: "insideLeft", fontSize: 11 }} />
                        <Tooltip />
                        <Legend verticalAlign="top" height={24} />
                        <Line data={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} dataKey="y" name="Chance (baseline)" stroke="var(--muted)" strokeDasharray="5 4" dot={false} isAnimationActive={false} />
                        <Line data={d.roc.map((p) => ({ x: p.fpr, y: p.tpr }))} dataKey="y" name="Your model (ROC)" stroke="var(--accent)" strokeWidth={2} dot={false} isAnimationActive={false} />
                        <Scatter data={d.cost_sweep.map((c) => ({ x: Number((1 - c.specificity).toFixed(3)), y: c.sensitivity, label: `${c.cost} to 1` }))} dataKey="y" name="Cost settings (1, 2, 4, 9 to 1)" fill="var(--danger, #d33)" isAnimationActive={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="mt-2 text-sm">Area under the curve: <b>{num(d.metrics.auc, 2)}</b> (0.5 is chance, 1.0 is perfect). The best setting is where the curve sits furthest above the dashed line for the balance of hits and false alarms you can afford. Chance of seeing accuracy this far above the simple guess by luck: <b>{d.metrics.p_vs_baseline != null && d.metrics.p_vs_baseline < 0.001 ? "under 0.1%" : num(d.metrics.p_vs_baseline, 3)}</b>.</p>
                </div>
              )}
              <p className="mt-2 text-xs text-muted">Raise the cost when a miss is expensive (a lost customer, a readmission) and a false alarm only wastes a little effort. Too high and the false alarms swamp you: pick the balance your costs justify, and say so in the write-up.</p>
            </Section>
          )}
          <Section title="The tree" note="Each box is a group of rows. The first line is the question that led there.">
            <ul className="space-y-1"><TreeNode n={d.tree} depth={0} /></ul>
          </Section>
          <Section title="Inputs the tree used"><Table head={["Input", "Weight"]} rows={d.importance.map((i) => [i.input, num(i.weight, 3)])} /></Section>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- sequential patterns
interface Seq {
  entities: number; entities_used: number; avg_length: number; sentences: string[]; warnings: string[]; lesson: string;
  steps: { from: string; to: string; count: number; probability: number }[]; paths: { path: string; count: number; customers_pct: number }[];
  starts: { event: string; count: number }[]; ends: { event: string; count: number }[];
}
export function SequenceTab({ base, cols }: { base: Base; cols: Col[] }) {
  const events = groupish(cols);
  const [entity, setEntity] = useState(cols.find((c) => c.kind === "text" && (c.distinct ?? 0) > 5)?.name ?? cols.find((c) => c.kind === "text")?.name ?? "");
  const [event, setEvent] = useState(events.find((c) => c.name !== entity)?.name ?? "");
  const [date, setDate] = useState(first(cols, "date"));
  const r = useRun<Seq>();
  if (events.length === 0 || !cols.some((c) => c.kind === "date")) return <p className="text-sm text-muted">Sequences need an event column with a few values (like step or status), a date column, and something to follow (like customer).</p>;
  const d = r.data;
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Sequential pattern mining follows what happens in order for each customer, order or device, for example from first visit to purchase.</p>
      <Section title="Follow events in order">
        <div className="grid gap-2 sm:grid-cols-3">
          <ColSelect label="Who or what to follow" value={entity} onChange={setEntity} cols={cols} kinds={["text", "number"]} />
          <ColSelect label="Event (what happened)" value={event} onChange={setEvent} cols={events} />
          <ColSelect label="Date column" value={date} onChange={setDate} cols={cols} kinds={["date"]} />
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !entity || !event || !date} onClick={() => r.run("/api/stats/sequences", { ...base, entity_col: entity, event_col: event, date_col: date })}>{r.busy ? "Tracing…" : "Find sequences"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} /><Sentences items={d.sentences} /><Warn items={d.warnings} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Followed" value={d.entities_used.toLocaleString()} sub={`of ${d.entities.toLocaleString()}`} />
            <Stat label="Typical length" value={num(d.avg_length, 1)} sub="steps" />
            <Stat label="Most common start" value={d.starts[0]?.event ?? "—"} sub={d.ends[0] ? `usual end: ${d.ends[0].event}` : undefined} />
          </div>
          <Section title="What usually comes next"><Table head={["After", "Next", "Times", "Chance of next"]} rows={d.steps.map((s) => [s.from, s.to, String(s.count), `${Math.round(s.probability * 100)}%`])} /></Section>
          {d.paths.length > 0 && <Section title="Common 3-step trails"><Table head={["Trail", "Times", "Share followed"]} rows={d.paths.map((p) => [p.path, String(p.count), `${p.customers_pct}%`])} /></Section>}
        </>
      )}
    </div>
  );
}
