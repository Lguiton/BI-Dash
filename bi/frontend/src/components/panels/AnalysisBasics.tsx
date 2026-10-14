"use client";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, Pie, PieChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, errMsg, num } from "./kit";
import { ColSelect, Lesson, Sentences, Warn, first, groupish, useRun, type Base, type Col } from "./analysisKit";

const PALETTE = ["#2f6f9f", "#d98f2b", "#4c9a6a", "#a05195", "#c4553b", "#6b7f8f", "#8a7d2a", "#3f8f8f"];
const pct = (v: number | null | undefined, d = 1) => (v == null ? "n/a" : `${(v * 100).toFixed(d)}%`);

// ---------------------------------------------------------------- frequency table, bar, pie and Pareto
interface Freq { column: string; total: number; distinct: number; sentences: string[]; lesson: string; table: { value: string; absolute: number; relative: number; cumulative: number }[] }
export function FrequencyTab({ base, cols }: { base: Base; cols: Col[] }) {
  const cats = [...groupish(cols), ...cols.filter((c) => c.kind === "text" && !groupish(cols).includes(c))];
  const [col, setCol] = useState(cats[0]?.name ?? "");
  const [view, setView] = useState<"pareto" | "bar" | "pie">("pareto");
  const r = useRun<Freq>();
  if (cats.length === 0) return <p className="text-sm text-muted">This data has no category columns. Use the Distribution tab for number columns.</p>;
  const d = r.data;
  return (
    <div className="space-y-4">
      <Section title="Frequency table">
        <p className="text-sm">Count how often each category occurs: <b>absolute</b> frequency (the count), <b>relative</b> frequency (the share) and <b>cumulative</b> frequency (the running share, reaching 100%). Sorted largest first with the cumulative line, it is a Pareto diagram: a few categories usually make up most of the total.</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <ColSelect label="Category column" value={col} onChange={setCol} cols={cats} />
          <Field label="Chart"><select className="field" value={view} onChange={(e) => setView(e.target.value as "pareto" | "bar" | "pie")}><option value="pareto">Pareto (bars and cumulative line)</option><option value="bar">Bar chart (counts)</option><option value="pie">Pie (share of the whole)</option></select></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !col} onClick={() => r.run("/api/stats/frequency", { ...base, column: col })}>{r.busy ? "Counting…" : "Build the table"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} /><Sentences items={d.sentences} />
          <div className="card h-80 min-w-0 p-3" role="img" aria-label={`${view} chart of ${d.column}`}>
            <ResponsiveContainer width="100%" height="100%">
              {view === "pie" ? (
                <PieChart><Tooltip /><Legend />
                  <Pie data={d.table.map((t) => ({ name: t.value, value: t.absolute }))} dataKey="value" nameKey="name" outerRadius="75%" label={(e) => `${((Number(e.value) / d.total) * 100).toFixed(0)}%`}>
                    {d.table.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                  </Pie></PieChart>
              ) : (
                <ComposedChart data={d.table.map((t) => ({ name: t.value, count: t.absolute, cum: Math.round(t.cumulative * 1000) / 10 }))} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                  <XAxis dataKey="name" stroke="var(--muted)" fontSize={11} interval={0} angle={d.table.length > 6 ? -30 : 0} textAnchor={d.table.length > 6 ? "end" : "middle"} height={d.table.length > 6 ? 60 : 30} />
                  <YAxis yAxisId="l" stroke="var(--muted)" fontSize={11} width={44} allowDecimals={false} />
                  {view === "pareto" && <YAxis yAxisId="r" orientation="right" domain={[0, 100]} unit="%" stroke="var(--muted)" fontSize={11} width={44} />}
                  <Tooltip /><Legend verticalAlign="top" height={24} />
                  <Bar yAxisId="l" dataKey="count" name="Count" fill="var(--accent)" />
                  {view === "pareto" && <Line yAxisId="r" dataKey="cum" name="Cumulative %" stroke="#d98f2b" strokeWidth={2} />}
                </ComposedChart>
              )}
            </ResponsiveContainer>
          </div>
          <Table head={[d.column, "Absolute", "Relative", "Cumulative"]} rows={d.table.map((t) => [t.value, num(t.absolute, 0), pct(t.relative), pct(t.cumulative)])} caption="Frequency distribution table" />
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- cross table
interface Cross { row_col: string; col_col: string; n: number; col_labels: string[]; col_totals: number[]; table: { row: string; counts: number[]; total: number; row_pct: (number | null)[] }[]; chi2: number; dof: number; p: number; cramers_v: number; strength: string; sentences: string[]; notes: string[]; lesson: string }
export function CrossTableTab({ base, cols }: { base: Base; cols: Col[] }) {
  const cats = groupish(cols);
  const [a, setA] = useState(cats[0]?.name ?? "");
  const [b, setB] = useState(cats[1]?.name ?? "");
  const [rel, setRel] = useState(false);
  const r = useRun<Cross>();
  if (cats.length < 2) return <p className="text-sm text-muted">A cross table needs two category columns with a few values each.</p>;
  const d = r.data;
  return (
    <div className="space-y-4">
      <Section title="Cross table (contingency table)">
        <p className="text-sm">Counts for every pair of two categories, with totals, plus a chi-square test of whether the two are linked. Show it as counts or as shares of each row.</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <ColSelect label="Rows" value={a} onChange={setA} cols={cats} />
          <ColSelect label="Columns" value={b} onChange={setB} cols={cats} />
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !a || !b || a === b} onClick={() => r.run("/api/stats/crosstab", { ...base, row_col: a, col_col: b })}>{r.busy ? "Working…" : "Build the cross table"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} /><Sentences items={d.sentences} /><Warn items={d.notes} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Rows counted" value={num(d.n, 0)} /><Stat label="Chi-square p-value" value={d.p < 0.001 ? "< 0.001" : d.p.toFixed(3)} sub={`${d.dof} degrees of freedom`} /><Stat label="Strength (Cramér's V)" value={d.cramers_v.toFixed(2)} sub={d.strength} />
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={rel} onChange={(e) => setRel(e.target.checked)} /> Show each row as a share of its total</label>
          <Table head={[`${d.row_col} \\ ${d.col_col}`, ...d.col_labels, "Total"]}
            rows={[...d.table.map((t) => [t.row, ...t.counts.map((c, i) => (rel ? pct(t.row_pct[i]) : num(c, 0))), rel ? "100%" : num(t.total, 0)]), ["Total", ...d.col_totals.map((c) => (rel ? pct(c / d.n) : num(c, 0))), rel ? "100%" : num(d.n, 0)]]} caption="Cross table" />
          <div className="card h-72 min-w-0 p-3" role="img" aria-label="Side-by-side bar chart of the cross table">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={d.table.map((t) => ({ name: t.row, ...Object.fromEntries(d.col_labels.map((c, i) => [c, t.counts[i]])) }))} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" /><XAxis dataKey="name" stroke="var(--muted)" fontSize={11} /><YAxis stroke="var(--muted)" fontSize={11} width={44} allowDecimals={false} /><Tooltip /><Legend />
                {d.col_labels.map((c, i) => <Bar key={c} dataKey={c} fill={PALETTE[i % PALETTE.length]} />)}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- hypothesis test for a mean, and margin of error calculator
interface MT { n: number; mean: number; sd_used: number; sd_kind: string; std_error: number; mu0: number; alternative: string; alpha: number; statistic: number; statistic_name: string; df: number | null; critical: number; rejection_region: string; p_value: number; reject: boolean; decision: string; ci: { level: number; low: number | null; high: number | null }; power: number; sentences: string[]; notes: string[]; lesson: string }
interface Margin { mode: string; margin_of_error?: number; n_needed?: number; reliability_factor: number; sentence: string }
export function HypothesisTab({ base, cols }: { base: Base; cols: Col[] }) {
  const [col, setCol] = useState(first(cols, "number"));
  const [mu0, setMu0] = useState("");
  const [alt, setAlt] = useState("two-sided");
  const [alpha, setAlpha] = useState(0.05);
  const [sigma, setSigma] = useState("");
  const r = useRun<MT>();
  const m = useRun<Margin>();
  const [msd, setMsd] = useState("");
  const [mmode, setMmode] = useState<"margin" | "n">("n");
  const [mval, setMval] = useState("");
  const [conf, setConf] = useState(0.95);
  if (!cols.some((c) => c.kind === "number")) return <p className="text-sm text-muted">This data has no number columns.</p>;
  const d = r.data;
  return (
    <div className="space-y-4">
      <Section title="Test a claim about an average">
        <p className="text-sm">Start from a claim (the <b>null hypothesis, H0</b>): the population average equals a value you choose. The <b>alternative (H1)</b> is what you suspect. Pick the significance level before you look. If you know the population standard deviation the test uses z; otherwise it uses Student&apos;s t with the sample&apos;s own spread.</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <ColSelect label="Number column" value={col} onChange={setCol} cols={cols} kinds={["number"]} />
          <Field label="Claimed average (H0)"><input className="field" type="number" value={mu0} onChange={(e) => setMu0(e.target.value)} /></Field>
          <Field label="Alternative (H1)"><select className="field" value={alt} onChange={(e) => setAlt(e.target.value)}><option value="two-sided">different (two-tailed)</option><option value="greater">greater than (one-tailed)</option><option value="less">less than (one-tailed)</option></select></Field>
          <Field label="Significance level (alpha)"><select className="field" value={alpha} onChange={(e) => setAlpha(Number(e.target.value))}><option value={0.01}>1%</option><option value={0.05}>5%</option><option value={0.1}>10%</option></select></Field>
          <Field label="Known population standard deviation (optional)"><input className="field" type="number" min={0} value={sigma} onChange={(e) => setSigma(e.target.value)} placeholder="leave empty to use the sample's" /></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !col || mu0 === ""} onClick={() => r.run("/api/stats/meantest", { ...base, column: col, mu0: Number(mu0), alternative: alt, alpha, sigma: sigma === "" ? null : Number(sigma) })}>{r.busy ? "Testing…" : "Run the test"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} /><Sentences items={d.sentences} /><Warn items={d.notes} />
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label={`${d.statistic_name}-statistic`} value={num(d.statistic, 3)} sub={d.df != null ? `${d.df} degrees of freedom` : "standard normal"} />
            <Stat label="p-value" value={d.p_value < 0.001 ? "< 0.001" : d.p_value.toFixed(4)} sub={`alpha ${d.alpha}`} />
            <Stat label="Decision" value={d.decision} sub={d.reject ? "evidence against H0" : "not enough evidence against H0"} />
            <Stat label="Power at this effect" value={`${Math.round(d.power * 100)}%`} sub="chance to detect it" />
          </div>
          <div className="card p-4 text-sm">
            <p><b>Rejection region:</b> {d.rejection_region}.</p>
            <p className="mt-1"><b>Confidence interval ({Math.round(d.ci.level * 100)}%):</b> {d.ci.low == null ? "no lower limit" : num(d.ci.low, 4)} to {d.ci.high == null ? "no upper limit" : num(d.ci.high, 4)}. <Badge>{d.sd_kind}</Badge></p>
          </div>
        </>
      )}
      <Section title="Margin of error and sample size">
        <p className="text-sm">The margin of error is half the width of a confidence interval. Work out the margin you would get from a sample size, or the sample size you need for a margin you want.</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-4">
          <Field label="Standard deviation"><input className="field" type="number" min={0} value={msd} onChange={(e) => setMsd(e.target.value)} /></Field>
          <Field label="I want to find"><select className="field" value={mmode} onChange={(e) => setMmode(e.target.value as "margin" | "n")}><option value="n">the sample size I need</option><option value="margin">the margin I would get</option></select></Field>
          <Field label={mmode === "n" ? "Target margin of error" : "Sample size"}><input className="field" type="number" min={0} value={mval} onChange={(e) => setMval(e.target.value)} /></Field>
          <Field label="Confidence"><select className="field" value={conf} onChange={(e) => setConf(Number(e.target.value))}><option value={0.9}>90%</option><option value={0.95}>95%</option><option value={0.99}>99%</option></select></Field>
        </div>
        <button className="btn mt-3" disabled={m.busy || !msd || !mval} onClick={() => m.run("/api/stats/margin", mmode === "n" ? { sd: Number(msd), margin: Number(mval), confidence: conf } : { sd: Number(msd), n: Number(mval), confidence: conf, population_sd_known: false })}>Calculate</button>
        {m.err && <div className="mt-2"><ErrorBanner message={m.err} /></div>}
        {m.data && <p className="mt-2 text-sm" role="status">{m.data.sentence}</p>}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- sampling distribution (central limit theorem)
interface Samp { population_rows: number; sample_size: number; repeats: number; population: { mean: number; sd: number; skewness: number; histogram: { x: number; count: number }[] }; sampling: { mean_of_means: number; std_error_observed: number; std_error_formula: number; skewness: number; histogram: { x: number; count: number }[] }; sentences: string[]; lesson: string }
export function SamplingTab({ base, cols }: { base: Base; cols: Col[] }) {
  const [col, setCol] = useState(first(cols, "number"));
  const [n, setN] = useState(30);
  const r = useRun<Samp>();
  if (!cols.some((c) => c.kind === "number")) return <p className="text-sm text-muted">This data has no number columns.</p>;
  const d = r.data;
  const chart = (data: { x: number; count: number }[], label: string, fill: string) => (
    <div className="card h-64 min-w-0 p-3" role="img" aria-label={label}>
      <div className="mb-1 text-xs font-medium text-muted">{label}</div>
      <ResponsiveContainer width="100%" height="90%"><BarChart data={data.map((h) => ({ x: num(h.x, 2), count: h.count }))} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}><CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" /><XAxis dataKey="x" stroke="var(--muted)" fontSize={10} minTickGap={24} /><YAxis stroke="var(--muted)" fontSize={10} width={36} allowDecimals={false} /><Tooltip /><Bar dataKey="count" fill={fill} /></BarChart></ResponsiveContainer>
    </div>
  );
  return (
    <div className="space-y-4">
      <Section title="Sampling distribution: watch the central limit theorem">
        <p className="text-sm">Treat your rows as the population, draw many random samples of a size you choose, and look at the distribution of their <b>means</b>. Whatever shape the data has, the means bunch into a bell shape around the true mean, with a spread (the <b>standard error</b>) of sigma divided by the square root of the sample size.</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          <ColSelect label="Number column" value={col} onChange={setCol} cols={cols} kinds={["number"]} />
          <Field label="Sample size"><select className="field" value={n} onChange={(e) => setN(Number(e.target.value))}>{[5, 10, 30, 100, 200].map((x) => <option key={x} value={x}>{x}</option>)}</select></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !col} onClick={() => r.run("/api/stats/sampling", { ...base, column: col, n, reps: 1000 })}>{r.busy ? "Drawing samples…" : "Draw 1,000 samples"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} /><Sentences items={d.sentences} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Mean of the sample means" value={num(d.sampling.mean_of_means, 3)} sub={`data mean ${num(d.population.mean, 3)}`} />
            <Stat label="Standard error (observed)" value={num(d.sampling.std_error_observed, 3)} sub={`formula ${num(d.sampling.std_error_formula, 3)}`} />
            <Stat label="Skewness" value={`${num(d.population.skewness, 2)} to ${num(d.sampling.skewness, 2)}`} sub="data, then sample means" />
          </div>
          <div className="grid gap-3 lg:grid-cols-2">{chart(d.population.histogram, "Your data", "#6b7f8f")}{chart(d.sampling.histogram, `Means of ${d.repeats.toLocaleString()} samples of ${d.sample_size}`, "var(--accent)")}</div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- data types and levels of measurement
interface VarT { column: string; kind: string; distinct: number; type: string; subtype?: string; level: string; group: string; note: string }
export function DataTypesTab({ source }: { source: string }) {
  const [d, setD] = useState<{ columns: VarT[]; lesson: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ columns: VarT[]; lesson: string }>(`/api/stats/variables?source=${encodeURIComponent(source)}`, ctl.signal).then(setD).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't classify the columns.")); });
    return () => ctl.abort();
  }, [source]);
  return (
    <div className="space-y-4">
      <Section title="What type of data is each column?">
        <p className="text-sm">Before choosing a chart or a statistic, know the type: <b>categorical</b> (groups) or <b>numerical</b> (discrete counts or continuous measures), and the level of measurement: <b>nominal</b> and <b>ordinal</b> (qualitative), <b>interval</b> and <b>ratio</b> (quantitative; ratio has a true zero). These are best guesses from the values. You know what the columns mean, so correct them in your head.</p>
        {err && <ErrorBanner message={err} />}
        {d && <Table head={["Column", "Type", "Level of measurement", "Distinct values", "Note"]} rows={d.columns.map((c) => [c.column, `${c.type}${c.subtype ? `, ${c.subtype}` : ""}`, `${c.group}: ${c.level}`, num(c.distinct, 0), c.note])} caption="Column types" />}
        {!d && !err && <p className="text-sm text-muted">Reading your columns…</p>}
        {d && <Lesson text={d.lesson} />}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- reference: formulas and spreadsheet functions
const FORMULAS: [string, string, string, string][] = [
  ["Mean", "sum of values / N", "=AVERAGE(range)", "Distribution tab"],
  ["Median", "middle value (position (n+1)/2)", "=MEDIAN(range)", "Distribution tab"],
  ["Mode", "most frequent value (0, 1 or several)", "=MODE.SNGL(range)  /  =MODE.MULT(range)", "Distribution tab, Frequency tab"],
  ["Skewness", "asymmetry around the mean", "=SKEW(range)", "Distribution tab"],
  ["Sample variance / sd", "sum((x - mean)^2) / (n - 1)", "=VAR.S(range)  /  =STDEV.S(range)", "Distribution tab"],
  ["Population variance / sd", "sum((x - mu)^2) / N", "=VAR.P(range)  /  =STDEV.P(range)", "Distribution tab"],
  ["Coefficient of variation", "sd / mean", "=STDEV.S(range)/AVERAGE(range)", "Distribution tab"],
  ["Covariance", "sum((x - mean_x)(y - mean_y)) / (n - 1)", "=COVARIANCE.S(x, y)  /  =COVARIANCE.P(x, y)", "Correlation tab"],
  ["Correlation", "covariance / (sd_x * sd_y)", "=CORREL(x, y)", "Correlation tab"],
  ["Count a category", "how many rows equal a value", "=COUNTIF(range, value)", "Frequency tab"],
  ["Histogram interval width", "(largest - smallest) / number of intervals", "=(MAX(range)-MIN(range))/k", "Distribution tab"],
  ["Count in an interval", "values from a to b", "=COUNTIF(range,\">=\"&a)-COUNTIF(range,\">\"&b)", "Distribution tab"],
  ["z-score", "(x - mean) / sd", "=STANDARDIZE(x, mean, sd)", "Data cleaning: Add a column, z-score"],
  ["Normal probability", "area under the bell curve", "=NORM.DIST(x, mean, sd, TRUE)", ""],
  ["Critical z / t", "reliability factor for a confidence level", "=NORM.S.INV(1-alpha/2)  /  =T.INV.2T(alpha, df)", "Hypothesis test tab"],
  ["Margin of error", "reliability factor x sd / sqrt(n)", "=CONFIDENCE.NORM(alpha, sd, n)  /  =CONFIDENCE.T(alpha, sd, n)", "Hypothesis test tab"],
  ["One-sample t-test p-value", "tail area beyond the t-statistic", "=T.DIST.2T(ABS(t), df)", "Hypothesis test tab"],
];
const CONCEPTS: [string, string][] = [
  ["Population vs sample", "A population (size N, described by parameters) is everything of interest; a sample (size n, described by statistics) is the part you have. A random sample picks members strictly by chance; a representative sample reflects the whole. Results from a sample are estimates."],
  ["Sample vs population formulas", "Sample variance and standard deviation divide by n - 1 so they are unbiased estimates of the population; population versions divide by N. Use the sample formulas unless your rows are the entire population."],
  ["Estimators", "An estimator is a rule (a point estimator gives one number; an interval estimator gives a range). The result is the estimate. Unbiased means right on average; efficient means little variability."],
  ["Confidence interval", "estimate +/- margin of error, with a confidence level (1 - alpha). Use z when the population sd is known, otherwise t with n - 1 degrees of freedom."],
  ["Hypothesis testing", "State H0 and H1, pick alpha, compute the test statistic, compare with the rejection region or the p-value. A Type I error (false positive) is rejecting a true H0; a Type II error (false negative) is missing a real effect; power = 1 - beta."],
  ["Normal and standardised", "The normal (Gaussian, bell-curve) distribution; the standard normal has mean 0 and sd 1; standardising a variable subtracts the mean and divides by the sd. By the central limit theorem, sample means are close to normal with standard error sigma / sqrt(n)."],
];
export function StatsRefTab() {
  return (
    <div className="space-y-4">
      <Section title="Key ideas">
        <dl className="space-y-2 text-sm">{CONCEPTS.map(([t, d]) => <div key={t}><dt className="font-medium">{t}</dt><dd className="text-muted">{d}</dd></div>)}</dl>
      </Section>
      <Section title="Formulas and spreadsheet functions" note="Names are Excel and Google Sheets; LibreOffice Calc uses the same names. Use them to check this app's answers by hand.">
        <Table head={["Measure", "Idea", "Spreadsheet function", "In this app"]} rows={FORMULAS.map((r) => r.map((c) => <span key={c} className="break-words">{c}</span>))} caption="Statistics formulas and functions" />
      </Section>
    </div>
  );
}
