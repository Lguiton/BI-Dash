"use client";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Badge, Field, Section, Stat, Table, num } from "./kit";
import { ColSelect, Lesson, Sentences, first, groupish, pv, useRun, type Base, type Col } from "./analysisKit";

const none = (msg: string) => <p className="text-sm text-muted">{msg}</p>;

// ---------------------------------------------------------------- distribution: centre, spread, shape, interval
interface Dist {
  n: number; sentences: string[]; lesson: string;
  central: { mean: number; median: number; mode: { value: number; count: number }[] };
  dispersion: { variance: number; sd: number; population_variance?: number; population_sd?: number; cv?: number | null; interval_width?: number; range: number; min: number; max: number; iqr: number; q1: number; q3: number };
  shape: { skewness: number | null; kurtosis: number | null; label: string };
  interval: { level: number; low: number; high: number; std_error: number };
  histogram: { from: number; to: number; count: number; relative?: number; cumulative?: number }[];
}
export function DistributionTab({ base, cols }: { base: Base; cols: Col[] }) {
  const [col, setCol] = useState(first(cols, "number"));
  const [conf, setConf] = useState(0.95);
  const r = useRun<Dist>();
  if (!cols.some((c) => c.kind === "number")) return none("This data has no number columns.");
  const d = r.data;
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">A <b>population</b> is everyone or everything of interest; a <b>sample</b> is the part you actually have. Descriptive statistics describe the sample (centre, spread, shape). The confidence interval is the inferential step: a range for the population value, allowing for sampling error.</p>
      <Section title="Describe one number column">
        <div className="grid gap-2 sm:grid-cols-3">
          <ColSelect label="Number column" value={col} onChange={setCol} cols={cols} kinds={["number"]} />
          <Field label="Confidence"><select className="field" value={conf} onChange={(e) => setConf(Number(e.target.value))}><option value={0.9}>90%</option><option value={0.95}>95%</option><option value={0.99}>99%</option></select></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !col} onClick={() => r.run("/api/stats/distribution", { ...base, column: col, confidence: conf })}>{r.busy ? "Working…" : "Describe"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} /><Sentences items={d.sentences} />
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="Mean" value={num(d.central.mean, 3)} sub={`median ${num(d.central.median, 3)}`} />
            <Stat label="Mode" value={d.central.mode[0] ? num(d.central.mode[0].value, 3) : "—"} sub={d.central.mode[0] ? `${d.central.mode[0].count} times` : undefined} />
            <Stat label="Standard deviation" value={num(d.dispersion.sd, 3)} sub={`variance ${num(d.dispersion.variance, 3)}`} />
            <Stat label="Range" value={num(d.dispersion.range, 3)} sub={`${num(d.dispersion.min, 2)} to ${num(d.dispersion.max, 2)}`} />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Middle half (IQR)" value={`${num(d.dispersion.q1, 2)} to ${num(d.dispersion.q3, 2)}`} sub={`width ${num(d.dispersion.iqr, 2)}`} />
            <Stat label="Shape" value={d.shape.label} sub={d.shape.skewness == null ? undefined : `skewness ${d.shape.skewness}`} />
            <Stat label={`${Math.round(d.interval.level * 100)}% interval for the mean`} value={`${num(d.interval.low, 3)} to ${num(d.interval.high, 3)}`} sub={`std. error ${num(d.interval.std_error, 3)}`} />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Population sd (if these rows are everything)" value={num(d.dispersion.population_sd, 3)} sub={`sample sd ${num(d.dispersion.sd, 3)}`} />
            <Stat label="Coefficient of variation" value={d.dispersion.cv == null ? "n/a" : `${(d.dispersion.cv * 100).toFixed(1)}%`} sub="sd as a share of the mean" />
            <Stat label="Histogram interval width" value={num(d.dispersion.interval_width, 3)} sub="(max - min) / intervals" />
          </div>
          <div className="card h-72 min-w-0 p-3" role="img" aria-label="Histogram of the column">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={d.histogram.map((h) => ({ x: num((h.from + h.to) / 2, 2), count: h.count }))} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                <XAxis dataKey="x" stroke="var(--muted)" fontSize={11} minTickGap={20} />
                <YAxis stroke="var(--muted)" fontSize={11} width={40} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" name="Rows" fill="var(--accent)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <Table head={["From", "To", "Count", "Relative", "Cumulative"]} rows={d.histogram.map((h) => [num(h.from, 3), num(h.to, 3), num(h.count, 0), h.relative == null ? "" : `${(h.relative * 100).toFixed(1)}%`, h.cumulative == null ? "" : `${(h.cumulative * 100).toFixed(1)}%`])} caption="Frequency table for the intervals" />
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- hypothesis test: compare groups
interface Cmp {
  sentences: string[]; notes: string[]; lesson: string;
  groups: { group: string; n: number; mean: number; sd: number; median: number }[];
  test: { name: string; statistic: number; p: number | null; difference?: number; ci_low?: number; ci_high?: number; effect_size: number; effect_label: string; backup_p: number | null; backup_name: string };
}
export function CompareTab({ base, cols }: { base: Base; cols: Col[] }) {
  const groupCols = groupish(cols);
  const [value, setValue] = useState(first(cols, "number"));
  const [group, setGroup] = useState(groupCols[0]?.name ?? "");
  const r = useRun<Cmp>();
  if (!cols.some((c) => c.kind === "number") || groupCols.length === 0) return none("Comparing groups needs a number column and a category column with 2 to 30 different values.");
  const t = r.data?.test;
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Hypothesis testing: do these groups really differ in the population, or could a gap this size appear by chance in a sample? Two groups use a Welch t-test; three or more use ANOVA. A rank-based check is shown as a backup.</p>
      <Section title="Do the groups differ?">
        <div className="grid gap-2 sm:grid-cols-2">
          <ColSelect label="Number to compare" value={value} onChange={setValue} cols={cols} kinds={["number"]} />
          <ColSelect label="Groups" value={group} onChange={setGroup} cols={groupCols} />
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !value || !group} onClick={() => r.run("/api/stats/compare", { ...base, value_col: value, group_col: group })}>{r.busy ? "Testing…" : "Run the test"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {r.data && t && (
        <>
          <Lesson text={r.data.lesson} /><Sentences items={r.data.sentences} />
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="Test" value={t.name.split(" (")[0]} sub={`statistic ${num(t.statistic, 2)}`} />
            <Stat label="p-value" value={pv(t.p)} sub={t.p != null && t.p < 0.05 ? "below 0.05" : "not below 0.05"} />
            <Stat label="Effect size" value={num(t.effect_size, 2)} sub={t.effect_label} />
            <Stat label={t.backup_name.split(" (")[0]} value={pv(t.backup_p)} sub="backup check" />
          </div>
          {t.difference != null && <p className="text-sm">Difference in averages: <b>{num(t.difference, 3)}</b> (95% interval {num(t.ci_low, 3)} to {num(t.ci_high, 3)}).</p>}
          <Table head={["Group", "Rows", "Average", "Median", "Standard deviation"]} rows={r.data.groups.map((g) => [g.group, String(g.n), num(g.mean, 3), num(g.median, 3), num(g.sd, 3)])} />
          <ul className="list-disc space-y-1 pl-5 text-xs text-muted">{r.data.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- correlation and scatter
interface Corr {
  rows_used: number; sentences: string[]; notes: string[]; lesson: string;
  pairs: { a: string; b: string; pearson: number | null; spearman: number | null; p: number | null; ci_low?: number | null; ci_high?: number | null; strength?: string; note?: string }[];
  scatter: { x: number; y: number }[] | null;
}
export function CorrelationTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const [sel, setSel] = useState<string[]>(nums.slice(0, 3).map((c) => c.name));
  const r = useRun<Corr>();
  if (nums.length < 2) return none("Correlation needs at least two number columns.");
  const d = r.data;
  return (
    <div className="space-y-4">
      <Section title="How do numbers move together?">
        <fieldset className="text-xs text-muted"><legend className="mb-1">Pick 2 to 8 number columns</legend>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm">{nums.map((c) => <label key={c.name} className="flex items-center gap-1"><input type="checkbox" checked={sel.includes(c.name)} onChange={() => setSel(sel.includes(c.name) ? sel.filter((x) => x !== c.name) : sel.length < 8 ? [...sel, c.name] : sel)} />{c.name}</label>)}</div></fieldset>
        <button className="btn btn-primary mt-3" disabled={r.busy || sel.length < 2} onClick={() => r.run("/api/stats/correlation", { ...base, columns: sel })}>{r.busy ? "Working…" : "Measure correlation"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} /><Sentences items={d.sentences} />
          <Table head={["Pair", "Pearson r", "Spearman", "95% interval", "p-value", "Reading"]} rows={d.pairs.map((p) => [`${p.a} and ${p.b}`, num(p.pearson, 3), num(p.spearman, 3), p.ci_low != null ? `${num(p.ci_low, 2)} to ${num(p.ci_high, 2)}` : "—", pv(p.p), p.strength ? <Badge key="s">{p.strength}</Badge> : p.note ?? "—"])} />
          {d.scatter && (
            <div className="card h-72 min-w-0 p-3" role="img" aria-label={`Scatter plot of ${sel[0]} against ${sel[1]}`}>
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 8, right: 12, bottom: 16, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                  <XAxis dataKey="x" name={sel[0]} type="number" stroke="var(--muted)" fontSize={11} domain={["auto", "auto"]} label={{ value: sel[0], position: "insideBottom", offset: -8, fontSize: 11 }} />
                  <YAxis dataKey="y" name={sel[1]} type="number" stroke="var(--muted)" fontSize={11} width={48} domain={["auto", "auto"]} />
                  <Tooltip />
                  <Scatter data={d.scatter} fill="var(--accent)" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          )}
          <ul className="list-disc space-y-1 pl-5 text-xs text-muted">{d.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </>
      )}
    </div>
  );
}
