"use client";
import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, ComposedChart, Legend, Line, ReferenceDot, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis, Area } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg, num } from "./kit";
import { ColSelect, CondEditor, Lesson, NO_VALUE, OPS, Sentences, Warn, first, groupish, pct, pv, useRun, type AType, type Base, type Col, type Cond, type Mode, type Source } from "./analysisKit";
import { CompareTab, CorrelationTab, DistributionTab } from "./AnalysisStats";
import { MiningGuideTab, SequenceTab, TreeTab } from "./AnalysisMining";
import { CleanTab, RollupTab } from "./AnalysisClean";
import { CookbookTab } from "./CookbookTab";
import { RelationalTab } from "./RelationalTab";
import { CrossTableTab, DataTypesTab, FrequencyTab, HypothesisTab, SamplingTab, StatsRefTab } from "./AnalysisBasics";
import { ArimaTab } from "./AnalysisForecast";
import { AssocTab, BusinessTab, ClusterTab, MlTab, OutlierTab } from "./AnalysisMore";
import { AllocTab, BeforeYouAct, BriefTab, GoalTab, TrackTab } from "./AnalysisPrescribe";
import { QualTab, ThemesTab } from "./AnalysisQual";
import { BigDataTab, ChallengesTab, ComponentsTab, DataPlanTab, FormatsTab, GatherImportTab, PrivacyTab, ReportTab, RequirementsTab, SourcesGuideTab, StoryTab, WrangleTab, ToolCategoriesTab, VizTab, MethodologyTab } from "./FoundationsPanel";

// ---------------------------------------------------------------- filter builder
function FilterBuilder({ cols, conds, setConds, mode, setMode }: { cols: Col[]; conds: Cond[]; setConds: (c: Cond[]) => void; mode: Mode; setMode: (m: Mode) => void }) {
  const upd = (i: number, patch: Partial<Cond>) => setConds(conds.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const kindOf = (name: string) => cols.find((c) => c.name === name)?.kind ?? "text";
  return (
    <div className="space-y-2">
      {conds.length === 0 && <p className="text-sm text-muted">No filters: every row is used. Add one to isolate the rows you care about (for example, leave out new customers before studying churn).</p>}
      {conds.map((c, i) => {
        const k = kindOf(c.column);
        return (
          <div key={i} className="flex flex-wrap items-end gap-2">
            <Field label={i === 0 ? "Column" : mode === "and" ? "and column" : "or column"}>
              <select className="field" value={c.column} onChange={(e) => upd(i, { column: e.target.value, op: OPS[kindOf(e.target.value)][0].id, value: "", value2: "" })}>
                {cols.map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
              </select>
            </Field>
            <Field label="Condition">
              <select className="field" value={c.op} onChange={(e) => upd(i, { op: e.target.value })}>{OPS[k].map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}</select>
            </Field>
            {!NO_VALUE.has(c.op) && (
              <Field label={c.op === "in" ? "Values (comma-separated)" : c.op === "between" ? "From" : "Value"}>
                {k === "bool" ? (
                  <select className="field" value={c.value || "true"} onChange={(e) => upd(i, { value: e.target.value })}><option value="true">true</option><option value="false">false</option></select>
                ) : (
                  <input className="field" type={k === "date" ? "date" : "text"} value={c.value} onChange={(e) => upd(i, { value: e.target.value })} />
                )}
              </Field>
            )}
            {c.op === "between" && <Field label="To"><input className="field" type={k === "date" ? "date" : "text"} value={c.value2} onChange={(e) => upd(i, { value2: e.target.value })} /></Field>}
            <button className="btn" aria-label={`Remove filter ${i + 1}`} onClick={() => setConds(conds.filter((_, j) => j !== i))}>Remove</button>
          </div>
        );
      })}
      <div className="flex flex-wrap items-end gap-2">
        <button className="btn" disabled={cols.length === 0 || conds.length >= 12} onClick={() => setConds([...conds, { column: cols[0].name, op: OPS[cols[0].kind][0].id, value: "", value2: "" }])}>Add filter</button>
        {conds.length > 1 && (
          <Field label="Keep rows that match">
            <select className="field" value={mode} onChange={(e) => setMode(e.target.value as Mode)}><option value="and">all filters (AND)</option><option value="or">any filter (OR)</option></select>
          </Field>
        )}
        {conds.length > 0 && <button className="btn" onClick={() => setConds([])}>Clear filters</button>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- the panel
type Method = "quant" | "qual" | "found";
const METHODS: { id: Method; label: string; blurb: string }[] = [
  { id: "quant", label: "Quantitative: numbers", blurb: "Crunch numbers: past results (margins, monthly revenue, burn) and future forecasts (regression, ARIMA-style, classification)." },
  { id: "qual", label: "Qualitative: judgement and context", blurb: "Words and judgement: post-mortems and observations for the past, SWOT, scenarios and pivot decisions for the future." },
  { id: "found", label: "Data foundations", blurb: "File formats, what big data means on this computer, and the common challenges of rolling out BI." },
];
const TABS: Record<Method, Record<string, { id: string; label: string }[]>> = {
  quant: {
    descriptive: [{ id: "summary", label: "Summary" }, { id: "trend", label: "Trends and patterns" }, { id: "types", label: "Data types" }, { id: "freq", label: "Frequency table" }, { id: "dist", label: "Distribution" }, { id: "cross", label: "Cross table" }, { id: "business", label: "Business metrics" }, { id: "filter", label: "Filtering" }],
    diagnostic: [{ id: "why", label: "What drives it" }, { id: "prob", label: "Probability" }, { id: "meantest", label: "Hypothesis test" }, { id: "compare", label: "Compare groups" }, { id: "sampling", label: "Sampling (CLT)" }, { id: "corr", label: "Correlation" }, { id: "reg", label: "Regression" }, { id: "outliers", label: "Outliers" }],
    predictive: [{ id: "forecast", label: "Forecast" }, { id: "reg", label: "Regression what-if" }, { id: "prob", label: "Probability" }, { id: "cluster", label: "Clusters" }, { id: "assoc", label: "Bought together" }, { id: "tree", label: "Decision tree" }, { id: "seq", label: "Sequences" }, { id: "ml", label: "Machine learning" }, { id: "mineguide", label: "Mining techniques" }],
    prescriptive: [{ id: "brief", label: "Decision brief" }, { id: "opps", label: "Opportunities and levers" }, { id: "goal", label: "Reach a goal" }, { id: "alloc", label: "Best allocation" }, { id: "track", label: "Track the result" }],
  },
  qual: {
    descriptive: [{ id: "observation", label: "Observations" }, { id: "themes", label: "Theme finder" }],
    diagnostic: [{ id: "postmortem", label: "Post-mortems" }, { id: "themes", label: "Theme finder" }],
    predictive: [{ id: "swot", label: "SWOT" }, { id: "scenario", label: "Scenario plan" }],
    prescriptive: [{ id: "premortem", label: "Pre-mortem" }, { id: "pivot", label: "Pivot decisions" }],
  },
  found: { all: [{ id: "method", label: "DS methodology" }, { id: "statref", label: "Statistics reference" }, { id: "formats", label: "File formats" }, { id: "bigdata", label: "Big data (practice)" }, { id: "challenges", label: "BI challenges" }, { id: "components", label: "BI components" }, { id: "toolcats", label: "BI tool categories" }, { id: "reqs", label: "BI project requirements" }, { id: "dataplan", label: "Identify the data" }, { id: "srcguide", label: "Where data comes from" }, { id: "gather", label: "Gather and import" }, { id: "wrangle", label: "Data wrangling" }, { id: "clean", label: "Data cleaning" }, { id: "cookbook", label: "SQL & pandas cookbook" }, { id: "relational", label: "Relational design" }, { id: "rollup", label: "One row per entity" }, { id: "viz", label: "Data visualization" }, { id: "story", label: "Data storytelling" }, { id: "report", label: "Findings report" }, { id: "privacy", label: "Privacy and security" }] },
};
const tabsFor = (m: Method, t: string) => TABS[m][t] ?? TABS[m].all;

function ForecastSwitch({ base, cols }: { base: Base; cols: Col[] }) {
  const [m, setM] = useState("trend");
  return (
    <div className="space-y-3">
      <Field label="Forecast method">
        <select className="field" value={m} onChange={(e) => setM(e.target.value)} aria-label="Forecast method">
          <option value="trend">Trend + repeating pattern (easy to explain)</option>
          <option value="arima">ARIMA-style (uses the series&apos; own recent past)</option>
        </select>
      </Field>
      {m === "trend" ? <TimeTab base={base} cols={cols} forecast /> : <ArimaTab base={base} cols={cols} />}
    </div>
  );
}

export function AnalysisPanel() {
  const [meta, setMeta] = useState<{ types: AType[]; sources: Source[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [method, setMethod] = useState<Method>("quant");
  const [type, setType] = useState("descriptive");
  const [tab, setTab] = useState("summary");
  const [sourceId, setSourceId] = useState("operations");
  const [conds, setConds] = useState<Cond[]>([]);
  const [mode, setMode] = useState<Mode>("and");

  useEffect(() => { getJson<{ types: AType[]; sources: Source[] }>("/api/stats/sources").then(setMeta).catch((e) => setErr(errMsg(e, "Couldn't load your data sources."))); }, []);
  const source = meta?.sources.find((s) => s.id === sourceId) ?? meta?.sources[0];
  const cols = useMemo(() => source?.columns.filter((c) => c.name !== "fact_id") ?? [], [source]);

  const base: Base | null = source ? {
    source: source.id, mode,
    filters: conds.filter((c) => c.column && (NO_VALUE.has(c.op) || (c.value !== "" && (c.op !== "between" || c.value2 !== ""))))
      .map((c) => ({ column: c.column, op: c.op, value: c.value, ...(c.op === "between" ? { value2: c.value2 } : {}) })),
  } : null;
  const ignored = conds.length - (base?.filters.length ?? 0);
  const filterKey = JSON.stringify(base);

  function pickMethod(m: Method) { setMethod(m); setTab(tabsFor(m, type)[0].id); }
  function pickType(id: string) { setType(id); setTab(tabsFor(method, id)[0].id); }
  function pickSource(id: string) { setSourceId(id); setConds([]); }

  const cur = meta?.types.find((t) => t.id === type);
  const curMethod = METHODS.find((m) => m.id === method);
  const prescriptive = method === "quant" && type === "prescriptive";
  const predictive = method === "quant" && type === "predictive";
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <div className="card space-y-3 p-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Method">
            <select className="field" value={method} onChange={(e) => pickMethod(e.target.value as Method)} aria-label="Method of analysis">
              {METHODS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </Field>
          {method !== "found" && (
            <Field label="Type of analytics">
              <select className="field" value={type} onChange={(e) => pickType(e.target.value)} aria-label="Type of analytics">
                {(meta?.types ?? [{ id: "descriptive", label: "Descriptive: what happened?", blurb: "" }]).map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </Field>
          )}
          {method !== "found" && (
            <Field label="Data to analyze">
              <select className="field" value={source?.id ?? ""} onChange={(e) => pickSource(e.target.value)} aria-label="Data to analyze">
                {(meta?.sources ?? []).map((s) => <option key={s.id} value={s.id}>{s.label}{s.rows != null ? ` (${s.rows.toLocaleString()} rows)` : ""}</option>)}
              </select>
            </Field>
          )}
        </div>
        <p className="text-sm text-muted">{curMethod?.blurb}{method !== "found" && cur ? ` ${cur.blurb}` : ""}</p>
        {method === "quant" && meta && meta.sources.length === 1 && <p className="text-xs text-muted">Tip: load a file in My data and it will appear in the data list here.</p>}
      </div>

      {method === "quant" && (
        <Section title={`Filters${base && base.filters.length ? ` (${base.filters.length} active)` : ""}`} note={ignored > 0 ? `${ignored} filter(s) with no value yet are ignored.` : "Filters apply to every tool on this page."}>
          {source ? <FilterBuilder cols={cols} conds={conds} setConds={setConds} mode={mode} setMode={setMode} /> : <p className="text-sm text-muted">Loading…</p>}
        </Section>
      )}

      <Tabs tabs={tabsFor(method, type)} value={tab} onChange={setTab} label="Analysis tools" />
      {method === "found" && <div key={tab}>{tab === "statref" ? <StatsRefTab /> : tab === "method" ? <MethodologyTab /> : tab === "formats" ? <FormatsTab /> : tab === "challenges" ? <ChallengesTab /> : tab === "components" ? <ComponentsTab /> : tab === "toolcats" ? <ToolCategoriesTab /> : tab === "reqs" ? <RequirementsTab /> : tab === "dataplan" ? <DataPlanTab /> : tab === "srcguide" ? <SourcesGuideTab /> : tab === "gather" ? <GatherImportTab /> : tab === "wrangle" ? <WrangleTab /> : tab === "relational" ? <RelationalTab /> : tab === "cookbook" ? <CookbookTab /> : tab === "clean" ? <CleanTab /> : tab === "rollup" ? <RollupTab /> : tab === "story" ? <StoryTab /> : tab === "viz" ? <VizTab /> : tab === "report" ? <ReportTab /> : tab === "privacy" ? <PrivacyTab /> : <BigDataTab />}</div>}
      {method === "qual" && (
        <div key={`${type}-${tab}`}>
          {tab === "themes" ? (source ? <ThemesTab source={source.id} cols={cols} /> : <p className="text-sm text-muted">Loading…</p>) : <QualTab kinds={[tab]} />}
        </div>
      )}
      {method === "quant" && source && base && cols.length > 0 && (
        <div key={`${type}-${tab}-${source.id}`} className="space-y-4">
          {prescriptive && <BeforeYouAct base={base} cols={cols} />}
          {tab === "summary" && <SummaryTab base={base} fk={filterKey} />}
          {tab === "trend" && <TimeTab base={base} cols={cols} forecast={false} />}
          {tab === "dist" && <DistributionTab base={base} cols={cols} />}
          {tab === "types" && <DataTypesTab source={base.source} />}
          {tab === "freq" && <FrequencyTab base={base} cols={cols} />}
          {tab === "cross" && <CrossTableTab base={base} cols={cols} />}
          {tab === "meantest" && <HypothesisTab base={base} cols={cols} />}
          {tab === "sampling" && <SamplingTab base={base} cols={cols} />}
          {tab === "compare" && <CompareTab base={base} cols={cols} />}
          {tab === "corr" && <CorrelationTab base={base} cols={cols} />}
          {tab === "business" && <BusinessTab base={base} cols={cols} />}
          {tab === "forecast" && <ForecastSwitch base={base} cols={cols} />}
          {tab === "filter" && <FilterTab base={base} fk={filterKey} />}
          {tab === "why" && <WhyTab base={base} cols={cols} />}
          {tab === "prob" && <ProbTab base={base} cols={cols} predictive={predictive} />}
          {tab === "reg" && <RegTab base={base} cols={cols} predictive={predictive} />}
          {tab === "outliers" && <OutlierTab base={base} cols={cols} />}
          {tab === "cluster" && <ClusterTab base={base} cols={cols} />}
          {tab === "assoc" && <AssocTab base={base} cols={cols} />}
          {tab === "tree" && <TreeTab base={base} cols={cols} />}
          {tab === "seq" && <SequenceTab base={base} cols={cols} />}
          {tab === "mineguide" && <MiningGuideTab />}
          {tab === "ml" && <MlTab base={base} cols={cols} />}
          {tab === "brief" && <BriefTab base={base} cols={cols} />}
          {tab === "opps" && <OppTab base={base} cols={cols} />}
          {tab === "goal" && <GoalTab base={base} cols={cols} />}
          {tab === "alloc" && <AllocTab base={base} cols={cols} />}
          {tab === "track" && <TrackTab base={base} cols={cols} />}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- descriptive: summary
interface Desc { rows: number; filters: string[]; numbers: { column: string; count: number; missing: number; mean: number | null; median: number | null; sd: number | null; min: number | null; q1: number | null; q3: number | null; max: number | null; sum: number | null; skew_note: string }[]; categories: { column: string; distinct: number; missing: number; top: { value: string; n: number; pct: number }[] }[]; dates: { column: string; from: string | null; to: string | null; missing: number }[]; sentences: string[]; lesson: string }
function SummaryTab({ base, fk }: { base: Base; fk: string }) {
  const r = useRun<Desc>();
  useEffect(() => {
    void r.run("/api/stats/describe", base);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fk]);
  return (
    <div className="space-y-4">
      {r.err && <ErrorBanner message={r.err} />}
      {r.busy && !r.data && <p className="text-sm text-muted">Summarizing…</p>}
      {r.data && (
        <>
          <Lesson text={r.data.lesson} />
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="Rows" value={r.data.rows.toLocaleString()} />
            <Stat label="Number columns" value={String(r.data.numbers.length)} />
            <Stat label="Category columns" value={String(r.data.categories.length)} />
            <Stat label="Date columns" value={String(r.data.dates.length)} sub={r.data.dates[0] ? `${r.data.dates[0].from} to ${r.data.dates[0].to}` : undefined} />
          </div>
          <Section title="Numbers: where the middle is and how spread out" note="Compare mean and median: a big gap means a few extreme values pull the average.">
            <Table head={["Column", "Mean", "Median", "Spread (sd)", "Min", "Q1", "Q3", "Max", "Missing", "Note"]}
              rows={r.data.numbers.map((n) => [n.column, num(n.mean, 2), num(n.median, 2), num(n.sd, 2), num(n.min, 2), num(n.q1, 2), num(n.q3, 2), num(n.max, 2), String(n.missing), <span key="n" className="text-xs text-muted">{n.skew_note}</span>])} />
          </Section>
          <Section title="Categories: what shows up most">
            <div className="grid gap-3 md:grid-cols-2">
              {r.data.categories.map((c) => (
                <div key={c.column} className="rounded border border-line p-3 text-sm">
                  <div className="mb-1 font-medium">{c.column} <Badge>{c.distinct} different</Badge></div>
                  <ul className="space-y-0.5">{c.top.map((t) => <li key={t.value} className="flex justify-between gap-2"><span className="truncate">{t.value}</span><span className="tabular-nums text-muted">{t.n.toLocaleString()} ({t.pct}%)</span></li>)}</ul>
                </div>
              ))}
            </div>
          </Section>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- filtering
interface FilterOut { total: number; kept: number; removed: number; kept_pct: number | null; funnel: { filter: string; matches_alone: number; rows_after: number }[]; summary: { column: string; mean_all: number | null; mean_kept: number | null; min_kept: number | null; max_kept: number | null }[]; columns: string[]; preview: Record<string, string | number | null>[]; sql: string; params: string[]; lesson: string }
function FilterTab({ base, fk }: { base: Base; fk: string }) {
  const r = useRun<FilterOut>();
  useEffect(() => {
    void r.run("/api/stats/filter", base);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fk]);
  return (
    <div className="space-y-4">
      {r.err && <ErrorBanner message={r.err} />}
      {r.data && (
        <>
          <Lesson text={r.data.lesson} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Rows before" value={r.data.total.toLocaleString()} />
            <Stat label="Rows kept" value={r.data.kept.toLocaleString()} sub={r.data.kept_pct == null ? undefined : `${r.data.kept_pct}% of all rows`} />
            <Stat label="Rows filtered out" value={r.data.removed.toLocaleString()} />
          </div>
          {r.data.funnel.length > 0 && (
            <Section title="What each filter does" note="'On its own' counts rows that pass that filter alone; 'running total' is what is left after combining it with the ones above.">
              <Table head={["Filter", "Rows passing on its own", "Running total kept"]} rows={r.data.funnel.map((f) => [f.filter, f.matches_alone.toLocaleString(), f.rows_after.toLocaleString()])} />
            </Section>
          )}
          {r.data.summary.length > 0 && (
            <Section title="Does filtering change the picture?" note="Averages before and after. A big shift means the rows you removed behave differently.">
              <Table head={["Column", "Average, all rows", "Average, kept rows", "Min kept", "Max kept"]} rows={r.data.summary.map((s) => [s.column, num(s.mean_all, 2), num(s.mean_kept, 2), num(s.min_kept, 2), num(s.max_kept, 2)])} />
            </Section>
          )}
          <Section title="Sample of the kept rows">
            {r.data.preview.length === 0 ? <p className="text-sm text-muted">No rows pass these filters.</p> :
              <Table head={r.data.columns} rows={r.data.preview.map((row) => r.data!.columns.map((c) => (row[c] == null ? "—" : String(row[c]))))} />}
          </Section>
          <Section title="The same filter as SQL" note="Values are passed separately (the ? marks) so they can never be run as code.">
            <pre className="overflow-x-auto rounded bg-panel2 p-3 text-xs">{r.data.sql}{r.data.params.length ? `\n-- ? = ${r.data.params.join(" | ")}` : ""}</pre>
          </Section>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- time series / forecast
interface Ts { available: boolean; reason?: string; bucket: string; agg: string; points: number; filled_gaps: number; window: number; series: { t: string; v: number; ma: number | null; trend: number; expected: number; anomaly: boolean }[]; forecast: { t: string; v: number; low: number; high: number }[]; trend: { slope: number; r2: number; p: number; direction: string; pct_of_mean: number | null }; seasonality: { kind: string; strength: number; pattern: { label: string; effect: number }[]; high: string; low: string } | null; anomalies: { t: string; value: number; expected: number; z: number; direction: string }[]; recent_change_pct: number | null; sentences: string[]; lesson: string }
function TimeTab({ base, cols, forecast }: { base: Base; cols: Col[]; forecast: boolean }) {
  const dates = cols.filter((c) => c.kind === "date");
  const [dateCol, setDateCol] = useState(first(cols, "date"));
  const [agg, setAgg] = useState("sum");
  const [value, setValue] = useState(first(cols, "number"));
  const [bucket, setBucket] = useState("day");
  const [horizon, setHorizon] = useState(14);
  const r = useRun<Ts>();
  if (dates.length === 0) return <p className="text-sm text-muted">This data has no date column, so there is no time to analyze. Load data with a date column in My data.</p>;
  const go = () => r.run("/api/stats/timeseries", { ...base, date_col: dateCol, value_col: agg === "count" ? null : value, agg, bucket, horizon: forecast ? horizon : 0 });
  const d = r.data && r.data.available ? r.data : null;
  const chartData = d ? [
    ...d.series.map((s) => ({ t: s.t, v: s.v, ma: s.ma, trend: s.trend })),
    ...d.forecast.map((f) => ({ t: f.t, fc: f.v, band: [f.low, f.high] as [number, number] })),
  ] : [];
  return (
    <div className="space-y-4">
      <Section title={forecast ? "Project it forward" : "Trend, repeating pattern and unusual points"}>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <ColSelect label="Date column" value={dateCol} onChange={setDateCol} cols={cols} kinds={["date"]} />
          <Field label="Measure"><select className="field" value={agg} onChange={(e) => setAgg(e.target.value)}><option value="sum">Total</option><option value="avg">Average</option><option value="count">Number of rows</option><option value="min">Smallest</option><option value="max">Largest</option></select></Field>
          {agg !== "count" && <ColSelect label="Of this column" value={value} onChange={setValue} cols={cols} kinds={["number"]} />}
          <Field label="Group by"><select className="field" value={bucket} onChange={(e) => setBucket(e.target.value)}><option value="day">Day</option><option value="week">Week</option><option value="month">Month</option></select></Field>
          {forecast && <Field label={`Look ahead (${bucket}s)`}><input className="field" type="number" min={1} max={60} value={horizon} onChange={(e) => setHorizon(Math.max(1, Math.min(60, Number(e.target.value) || 1)))} /></Field>}
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || (agg !== "count" && !value)} onClick={go}>{r.busy ? "Working…" : forecast ? "Forecast" : "Analyze"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {r.data && !r.data.available && <p className="rounded border border-line p-3 text-sm">{r.data.reason}</p>}
      {d && (
        <>
          <Lesson text={d.lesson} />
          <Sentences items={d.sentences} />
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="Periods" value={String(d.points)} sub={d.filled_gaps ? `${d.filled_gaps} gap(s) filled` : undefined} />
            <Stat label="Trend" value={d.trend.direction} sub={`R² ${num(d.trend.r2, 2)}, p ${pv(d.trend.p)}`} />
            <Stat label="Pattern strength" value={d.seasonality ? pct(d.seasonality.strength, 0) : "n/a"} sub={d.seasonality ? `${d.seasonality.kind} cycle` : "needs 2 full cycles"} />
            <Stat label="Unusual points" value={String(d.anomalies.length)} sub={d.recent_change_pct == null ? undefined : `latest ${d.window}: ${d.recent_change_pct > 0 ? "+" : ""}${d.recent_change_pct}%`} />
          </div>
          <div className="card h-80 min-w-0 p-3" role="img" aria-label="Line chart of the measure over time with trend line, moving average and anomalies">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                <XAxis dataKey="t" stroke="var(--muted)" fontSize={11} tickFormatter={(x: string) => x.slice(5)} minTickGap={24} />
                <YAxis stroke="var(--muted)" fontSize={11} width={56} tickFormatter={(x: number) => num(x, 0)} />
                <Tooltip />
                <Legend />
                {forecast && <Area dataKey="band" name="95% range" stroke="none" fill="var(--accent)" fillOpacity={0.15} />}
                <Line dataKey="v" name="Actual" stroke="var(--c-revenue)" strokeWidth={1.5} dot={false} connectNulls />
                <Line dataKey="ma" name={`${d.window}-period average`} stroke="var(--cat-2)" strokeWidth={2} dot={false} connectNulls />
                <Line dataKey="trend" name="Trend" stroke="var(--cat-3)" strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
                {forecast && <Line dataKey="fc" name="Forecast" stroke="var(--accent)" strokeWidth={2} strokeDasharray="6 4" dot={{ r: 2 }} />}
                {d.anomalies.map((a) => <ReferenceDot key={a.t} x={a.t} y={a.value} r={5} fill="var(--bad)" stroke="none" ifOverflow="extendDomain" />)}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {d.seasonality && (
              <Section title={`Repeating ${d.seasonality.kind} pattern`} note="How far above (+) or below (−) the trend each position usually runs.">
                <Table head={[d.seasonality.kind === "weekday" ? "Weekday" : "Month", "Usual effect"]} rows={d.seasonality.pattern.map((p) => [p.label, <span key="e" style={{ color: p.effect >= 0 ? "var(--good)" : "var(--bad)" }}>{p.effect >= 0 ? "+" : ""}{num(p.effect, 2)}</span>])} />
              </Section>
            )}
            <Section title="Unusual points" note="Far from what trend and pattern predicted (robust z-score above 3.5). Check them: errors, one-off events or real changes.">
              {d.anomalies.length === 0 ? <p className="text-sm text-muted">Nothing stands out.</p> :
                <Table head={["When", "Actual", "Expected", "z", ""]} rows={d.anomalies.map((a) => [a.t, num(a.value, 2), num(a.expected, 2), num(a.z, 1), <Badge key="b" tone="warn">{a.direction}</Badge>])} />}
            </Section>
          </div>
          {forecast && d.forecast.length > 0 && (
            <Section title="Forecast table" note="Assumes the past trend and pattern continue. It cannot see price changes, holidays or news.">
              <Table head={["When", "Expected", "Low (95%)", "High (95%)"]} rows={d.forecast.map((f) => [f.t, num(f.v, 2), num(f.low, 2), num(f.high, 2)])} />
            </Section>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- probability
interface Prob { event: string; filters: string[]; rows_used: number; events: number; p: number; ci_low: number; ci_high: number; sentences: string[]; warnings: string[]; groups?: { group: string; n: number; events: number; p: number; ci_low: number; ci_high: number; lift: number | null; small: boolean }[]; independence_p?: number; bayes?: { given: string; p_a: number; p_b: number; p_a_and_b: number; p_a_given_b: number | null; p_b_given_a: number | null; p_a_given_not_b: number | null; lift: number | null; independence_p?: number; counts: { n: number; a: number; b: number; ab: number } }; repeat?: { entity_col: string; entities_with_event: number; entities_repeating: number; p_repeat: number | null; ci_low: number | null; ci_high: number | null; distribution: { times: number; entities: number }[] }; lesson: string }
function ProbTab({ base, cols, predictive }: { base: Base; cols: Col[]; predictive: boolean }) {
  const textCols = cols.filter((c) => c.kind === "text" || c.kind === "bool");
  const start = groupish(cols)[0] ?? textCols[0] ?? cols[0];
  const [ev, setEv] = useState<Cond>({ column: start.name, op: "eq", value: "", value2: "" });
  const [group, setGroup] = useState("");
  const [useGiven, setUseGiven] = useState(false);
  const [given, setGiven] = useState<Cond>({ column: (groupish(cols)[1] ?? textCols[1] ?? start).name, op: "eq", value: "", value2: "" });
  const [entity, setEntity] = useState("");
  const r = useRun<Prob>();
  const ready = NO_VALUE.has(ev.op) || ev.value !== "";
  const go = () => r.run("/api/stats/probability", { ...base, event: ev, group_by: group || null, given: useGiven ? given : null, entity_col: entity || null });
  const d = r.data;
  return (
    <div className="space-y-4">
      <Section title={predictive ? "How likely is it?" : "How often does it happen, and when more?"}
        note="Probability from history = times it happened ÷ times it could have. Example: the chance a customer makes a purchase, or an order is returned.">
        <div className="space-y-3">
          <CondEditor label="The event" cols={cols} c={ev} set={setEv} />
          <div className="grid gap-2 sm:grid-cols-3">
            <ColSelect label="Compare across groups (optional)" value={group} onChange={setGroup} cols={textCols} none="No grouping" />
            <ColSelect label="Does the same one do it again? Who (optional)" value={entity} onChange={setEntity} cols={cols.filter((c) => c.kind !== "date")} none="Skip" />
            <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" checked={useGiven} onChange={(e) => setUseGiven(e.target.checked)} /> Add a second condition (conditional probability)</label>
          </div>
          {useGiven && <CondEditor label="Given that" cols={cols} c={given} set={setGiven} />}
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !ready || (useGiven && !NO_VALUE.has(given.op) && given.value === "")} onClick={go}>{r.busy ? "Working…" : "Calculate"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} />
          <Warn items={d.warnings} />
          <Sentences items={d.sentences} />
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="Probability" value={pct(d.p)} sub={`95% range ${pct(d.ci_low)} to ${pct(d.ci_high)}`} />
            <Stat label="Times it happened" value={d.events.toLocaleString()} />
            <Stat label="Rows measured" value={d.rows_used.toLocaleString()} />
            {d.independence_p != null && <Stat label="Groups differ?" value={d.independence_p < 0.05 ? "Yes, likely" : "Maybe luck"} sub={`chi-square p ${pv(d.independence_p)}`} />}
          </div>
          {d.groups && (
            <Section title={`By ${group}`} note="Lift = the group's chance ÷ the overall chance (above 1 means more likely). Groups with fewer than 30 rows are marked; don't lean on them.">
              <Table head={[group, "Rows", "Happened", "Probability", "95% range", "Lift", ""]}
                rows={d.groups.map((g) => [g.group, g.n.toLocaleString(), g.events.toLocaleString(), pct(g.p), `${pct(g.ci_low)} to ${pct(g.ci_high)}`, g.lift == null ? "—" : g.lift.toFixed(2), g.small ? <Badge key="s" tone="warn">small sample</Badge> : ""])} />
            </Section>
          )}
          {d.bayes && (
            <Section title={`Given: ${d.bayes.given}`} note="A = the event, B = the second condition. P(A | B) means: among rows where B is true, how often is A true?">
              <div className="grid gap-3 sm:grid-cols-4">
                <Stat label="P(A)" value={pct(d.bayes.p_a)} /><Stat label="P(B)" value={pct(d.bayes.p_b)} />
                <Stat label="P(A and B)" value={pct(d.bayes.p_a_and_b)} /><Stat label="P(A | B)" value={pct(d.bayes.p_a_given_b)} sub={d.bayes.lift == null ? undefined : `lift ${d.bayes.lift.toFixed(2)}`} />
                <Stat label="P(B | A)" value={pct(d.bayes.p_b_given_a)} /><Stat label="P(A | not B)" value={pct(d.bayes.p_a_given_not_b)} />
                {d.bayes.independence_p != null && <Stat label="Independent?" value={d.bayes.independence_p < 0.05 ? "No, linked" : "Could be"} sub={`p ${pv(d.bayes.independence_p)}`} />}
              </div>
            </Section>
          )}
          {d.repeat && (
            <Section title={`Does the same ${d.repeat.entity_col} do it again?`} note="Of the values that had the event at least once, the share that had it two or more times.">
              <div className="grid gap-3 sm:grid-cols-3">
                <Stat label="Had it at least once" value={d.repeat.entities_with_event.toLocaleString()} />
                <Stat label="Did it again" value={d.repeat.entities_repeating.toLocaleString()} />
                <Stat label="Repeat chance" value={pct(d.repeat.p_repeat)} sub={`95% range ${pct(d.repeat.ci_low)} to ${pct(d.repeat.ci_high)}`} />
              </div>
              <div className="mt-3"><Table head={["Times", `${d.repeat.entity_col} values`]} rows={d.repeat.distribution.map((x) => [String(x.times), x.entities.toLocaleString()])} /></div>
            </Section>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- regression
interface Reg { y: string; n: number; params: number; r2: number; adj_r2: number; rmse: number; mae: number; f_stat: number | null; f_p: number | null; coefficients: { term: string; coef: number; se: number; t: number; p: number; ci_low: number; ci_high: number; std_coef: number | null; significant: boolean | null }[]; vif: { term: string; vif: number | null }[]; holdout: { r2: number | null; rows: number } | null; reference: Record<string, string>; chart: { kind: string; x: string; y: string; points: { x: number; y: number }[]; line: { x: number; y: number }[] }; residuals: { x: number; y: number }[]; what_if: { inputs: string[]; prediction: number; low: number; high: number } | null; warnings: string[]; sentences: string[]; lesson: string }
function RegTab({ base, cols, predictive }: { base: Base; cols: Col[]; predictive: boolean }) {
  const nums = cols.filter((c) => c.kind === "number");
  const cats = cols.filter((c) => c.kind === "text" || c.kind === "bool");
  const [y, setY] = useState(nums[0]?.name ?? "");
  const [xn, setXn] = useState<string[]>(nums.slice(1, 3).map((c) => c.name));
  const [xc, setXc] = useState<string[]>([]);
  const [vals, setVals] = useState<Record<string, string>>({});
  const r = useRun<Reg>();
  if (nums.length < 2) return <p className="text-sm text-muted">Regression needs at least two number columns (one to explain, one or more inputs).</p>;
  const toggle = (arr: string[], set: (a: string[]) => void, n: string) => set(arr.includes(n) ? arr.filter((x) => x !== n) : [...arr, n]);
  const wantsWhatIf = predictive && xn.every((c) => vals[c] !== undefined && vals[c] !== "");
  const go = () => r.run("/api/stats/regression", { ...base, y, x_numeric: xn.filter((c) => c !== y), x_categorical: xc, predict: wantsWhatIf ? { ...vals, ...Object.fromEntries(xc.filter((c) => vals[c]).map((c) => [c, vals[c]])) } : null });
  const d = r.data;
  return (
    <div className="space-y-4">
      <Section title={predictive ? "Predict one number from others" : "Which inputs move the result, and by how much?"} note="Linear regression draws the best straight-line fit. It shows association, not cause.">
        <div className="grid gap-3 md:grid-cols-3">
          <ColSelect label="Number to explain (Y)" value={y} onChange={(v) => { setY(v); setXn(xn.filter((c) => c !== v)); r.reset(); }} cols={nums} />
          <fieldset className="min-w-0 text-xs text-muted"><legend className="mb-1">Number inputs (X)</legend>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm">{nums.filter((c) => c.name !== y).map((c) => <label key={c.name} className="flex items-center gap-1"><input type="checkbox" checked={xn.includes(c.name)} onChange={() => toggle(xn, setXn, c.name)} />{c.name}</label>)}</div>
          </fieldset>
          <fieldset className="min-w-0 text-xs text-muted"><legend className="mb-1">Category inputs (optional)</legend>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-sm">{cats.length === 0 ? <span className="text-muted">none in this data</span> : cats.map((c) => <label key={c.name} className="flex items-center gap-1"><input type="checkbox" checked={xc.includes(c.name)} onChange={() => toggle(xc, setXc, c.name)} />{c.name}</label>)}</div>
          </fieldset>
        </div>
        {predictive && xn.length > 0 && (
          <div className="mt-3">
            <p className="mb-1 text-xs text-muted">What-if (optional): type a value for every number input to get a prediction with a 95% range.</p>
            <div className="grid gap-2 sm:grid-cols-4">{xn.map((c) => <Field key={c} label={c}><input className="field" inputMode="decimal" value={vals[c] ?? ""} onChange={(e) => setVals({ ...vals, [c]: e.target.value })} /></Field>)}</div>
          </div>
        )}
        <button className="btn btn-primary mt-3" disabled={r.busy || (xn.length === 0 && xc.length === 0)} onClick={go}>{r.busy ? "Working…" : "Run regression"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} />
          <Warn items={d.warnings} />
          <Sentences items={d.sentences} />
          <div className="grid gap-3 sm:grid-cols-4">
            <Stat label="R² (fit)" value={pct(d.r2, 0)} sub={`adjusted ${pct(d.adj_r2, 0)}`} />
            <Stat label="Typical miss (RMSE)" value={num(d.rmse, 2)} sub={`average miss ${num(d.mae, 2)}`} />
            <Stat label="Rows used" value={d.n.toLocaleString()} />
            <Stat label="On rows it didn't learn" value={d.holdout?.r2 == null ? "n/a" : pct(d.holdout.r2, 0)} sub={d.holdout ? `R² on ${d.holdout.rows} held-out rows` : "needs 50+ rows"} />
          </div>
          {d.what_if && (
            <div className="card p-4 text-sm">
              <div className="text-xs uppercase tracking-wide text-muted">What-if prediction ({d.what_if.inputs.join(", ")})</div>
              <div className="text-2xl font-bold tabular-nums">{num(d.what_if.prediction, 2)}</div>
              <div className="text-xs text-muted">95% range for a single new case: {num(d.what_if.low, 2)} to {num(d.what_if.high, 2)}</div>
            </div>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <Section title={d.chart.kind === "scatter" ? `${d.chart.y} vs ${d.chart.x}` : "Predicted vs actual"} note={d.chart.kind === "scatter" ? "Dots are rows (a sample); the line is the fit." : "Points on the line are perfect predictions."}>
              <div className="h-72"><ResponsiveContainer width="100%" height="100%">
                <ComposedChart margin={{ top: 8, right: 12, bottom: 16, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                  <XAxis type="number" dataKey="x" name={d.chart.x} stroke="var(--muted)" fontSize={11} domain={["auto", "auto"]} tickFormatter={(x: number) => num(x, 0)} label={{ value: d.chart.x, position: "insideBottom", offset: -8, fontSize: 11 }} />
                  <YAxis type="number" dataKey="y" name={d.chart.y} stroke="var(--muted)" fontSize={11} width={56} domain={["auto", "auto"]} tickFormatter={(x: number) => num(x, 0)} />
                  <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                  <Scatter data={d.chart.points} fill="var(--c-revenue)" fillOpacity={0.5} name="Rows" />
                  <Line data={d.chart.line} dataKey="y" stroke="var(--bad)" strokeWidth={2} dot={false} name="Fit" legendType="none" />
                </ComposedChart></ResponsiveContainer></div>
            </Section>
            <Section title="Errors vs predicted" note="Should look like an even cloud. A funnel or curve means a straight line is missing something.">
              <div className="h-72"><ResponsiveContainer width="100%" height="100%">
                <ComposedChart margin={{ top: 8, right: 12, bottom: 16, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                  <XAxis type="number" dataKey="x" name="predicted" stroke="var(--muted)" fontSize={11} domain={["auto", "auto"]} tickFormatter={(x: number) => num(x, 0)} label={{ value: "predicted", position: "insideBottom", offset: -8, fontSize: 11 }} />
                  <YAxis type="number" dataKey="y" name="error" stroke="var(--muted)" fontSize={11} width={56} domain={["auto", "auto"]} tickFormatter={(x: number) => num(x, 0)} />
                  <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                  <Scatter data={d.residuals} fill="var(--cat-3)" fillOpacity={0.5} name="Error" />
                </ComposedChart></ResponsiveContainer></div>
            </Section>
          </div>
          <Section title="The numbers" note={`Each coefficient is the average change in ${d.y} for +1 in that input, other inputs fixed. 'Reliable' means p below 0.05. Std. effect lets you compare inputs measured in different units.${Object.keys(d.reference).length ? ` Category rows compare with: ${Object.entries(d.reference).map(([k, v]) => `${k} = ${v}`).join(", ")}.` : ""}`}>
            <Table head={["Input", "Effect", "95% range", "p", "Std. effect", ""]}
              rows={d.coefficients.map((c) => [c.term, num(c.coef, 4), `${num(c.ci_low, 3)} to ${num(c.ci_high, 3)}`, pv(c.p), c.std_coef == null ? "—" : num(c.std_coef, 2), c.significant == null ? "" : <Badge key="s" tone={c.significant ? "ok" : "muted"}>{c.significant ? "reliable" : "unclear"}</Badge>])} />
            {d.vif.length > 0 && <p className="mt-2 text-xs text-muted">Overlap check (VIF; above 5 is a concern): {d.vif.map((v) => `${v.term} ${v.vif ?? "∞"}`).join(", ")}</p>}
          </Section>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- diagnostic: what drives it
interface Diag { y: string; rows: number; drivers: { column: string; kind: string; strength: number; detail: string; n: number }[]; change: { split: string; from: string; to: string; total_before: number; total_after: number; change: number; change_pct: number | null; group_col: string | null; parts: { group: string; before: number; after: number; change: number; share_of_change: number | null; rows_before: number; rows_after: number }[] } | null; sentences: string[]; lesson: string }
function WhyTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const [y, setY] = useState(nums[0]?.name ?? "");
  const [group, setGroup] = useState(groupish(cols)[0]?.name ?? "");
  const [date, setDate] = useState(first(cols, "date"));
  const [split, setSplit] = useState("");
  const r = useRun<Diag>();
  if (nums.length === 0) return <p className="text-sm text-muted">This data has no number column to explain.</p>;
  const go = () => r.run("/api/stats/diagnose", { ...base, y, group_col: group || null, date_col: date || null, split: split || null });
  const d = r.data;
  return (
    <div className="space-y-4">
      <Section title="Why did it change?" note="Step 1: which columns move with your number. Step 2: split a change between two periods by group to see where it came from.">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <ColSelect label="Number to explain" value={y} onChange={setY} cols={nums} />
          <ColSelect label="Split the change by" value={group} onChange={setGroup} cols={cols.filter((c) => c.kind === "text" || c.kind === "bool")} none="No split" />
          <ColSelect label="Compare periods using" value={date} onChange={setDate} cols={cols} kinds={["date"]} none="Skip" />
          {date && <Field label="Compare before/after (blank = midpoint)"><input className="field" type="date" value={split} onChange={(e) => setSplit(e.target.value)} /></Field>}
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !y} onClick={go}>{r.busy ? "Working…" : "Find the drivers"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} />
          <Sentences items={d.sentences} />
          <Section title={`What moves with ${d.y}`} note="Number columns show correlation (−1 to +1, strength shown as 0 to 1). Category columns show the share of variation their groups explain. These are leads, not proof; test them with Regression.">
            <Table head={["Column", "Type", "Strength", "Detail"]} rows={d.drivers.map((x) => [x.column, x.kind, <div key="b" className="flex items-center gap-2"><div className="h-2 w-24 rounded bg-panel2"><div className="h-2 rounded" style={{ width: `${Math.round(x.strength * 100)}%`, background: "var(--accent)" }} /></div><span className="tabular-nums">{x.strength.toFixed(2)}</span></div>, x.detail])} />
          </Section>
          {d.change && (
            <Section title={`Where the change came from (split at ${d.change.split})`} note="Totals before and from the split date. If the two periods have different numbers of rows, part of the change is just volume; check the row counts.">
              <div className="mb-3 grid gap-3 sm:grid-cols-3">
                <Stat label="Before" value={num(d.change.total_before, 0)} /><Stat label="After" value={num(d.change.total_after, 0)} />
                <Stat label="Change" value={`${d.change.change > 0 ? "+" : ""}${num(d.change.change, 0)}`} sub={d.change.change_pct == null ? undefined : `${d.change.change_pct > 0 ? "+" : ""}${d.change.change_pct}%`} />
              </div>
              <Table head={[d.change.group_col ?? "Group", "Before", "After", "Change", "Share of change", "Rows before → after"]}
                rows={d.change.parts.map((p) => [p.group, num(p.before, 0), num(p.after, 0), <span key="c" style={{ color: p.change >= 0 ? "var(--good)" : "var(--bad)" }}>{p.change >= 0 ? "+" : ""}{num(p.change, 0)}</span>, p.share_of_change == null ? "—" : `${p.share_of_change}%`, `${p.rows_before.toLocaleString()} → ${p.rows_after.toLocaleString()}`])} />
            </Section>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- prescriptive
interface Opp { metric: string; group_col: string; benchmark: number; benchmark_kind: string; groups: number; best_group: string; opportunities: { group: string; rows: number; average: number; benchmark: number; gap_per_row: number; estimated_gain: number; action: string }[]; sentences: string[]; levers: { y: string; r2: number; note: string; items: { lever: string; coef: number; effect_of_plus_10pct: number; reliable: boolean; std_coef: number | null }[] } | null; lesson: string }
function OppTab({ base, cols }: { base: Base; cols: Col[] }) {
  const nums = cols.filter((c) => c.kind === "number");
  const cats = cols.filter((c) => c.kind === "text" || c.kind === "bool");
  const [metric, setMetric] = useState(nums[0]?.name ?? "");
  const [group, setGroup] = useState((groupish(cols)[0] ?? cats[0])?.name ?? "");
  const [hib, setHib] = useState(true);
  const [bench, setBench] = useState("median");
  const [minRows, setMinRows] = useState(5);
  const [useLevers, setUseLevers] = useState(false);
  const [levers, setLevers] = useState<string[]>(nums.slice(1, 3).map((c) => c.name));
  const r = useRun<Opp>();
  if (nums.length === 0 || cats.length === 0) return <p className="text-sm text-muted">This needs a number column to improve and a category column to compare (for example revenue by region).</p>;
  const go = () => r.run("/api/stats/opportunities", { ...base, value_col: metric, group_col: group, higher_is_better: hib, benchmark: bench, min_rows: minRows, levers_y: useLevers ? metric : null, levers: useLevers ? levers.filter((l) => l !== metric) : [] });
  const d = r.data;
  return (
    <div className="space-y-4">
      <Section title="Where would effort pay off most?" note="Groups that trail the benchmark, ranked by (gap per row × number of rows). Sized from history; each is something to test, not a promise.">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <ColSelect label="Number to improve" value={metric} onChange={setMetric} cols={nums} />
          <ColSelect label="Compare these groups" value={group} onChange={setGroup} cols={cats} />
          <Field label="Better means"><select className="field" value={hib ? "high" : "low"} onChange={(e) => setHib(e.target.value === "high")}><option value="high">higher (revenue, profit)</option><option value="low">lower (cost, delay)</option></select></Field>
          <Field label="Aim to match"><select className="field" value={bench} onChange={(e) => setBench(e.target.value)}><option value="median">the typical group</option><option value="top_quartile">a top-quarter group</option><option value="best">the best group</option></select></Field>
          <Field label="Ignore groups under N rows"><input className="field" type="number" min={1} value={minRows} onChange={(e) => setMinRows(Math.max(1, Number(e.target.value) || 1))} /></Field>
        </div>
        <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={useLevers} onChange={(e) => setUseLevers(e.target.checked)} /> Also rank the levers (which inputs move this number most)</label>
        {useLevers && <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm">{nums.filter((c) => c.name !== metric).map((c) => <label key={c.name} className="flex items-center gap-1"><input type="checkbox" checked={levers.includes(c.name)} onChange={() => setLevers(levers.includes(c.name) ? levers.filter((x) => x !== c.name) : [...levers, c.name])} />{c.name}</label>)}</div>}
        <button className="btn btn-primary mt-3" disabled={r.busy} onClick={go}>{r.busy ? "Working…" : "Find opportunities"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {d && (
        <>
          <Lesson text={d.lesson} />
          <Sentences items={d.sentences} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Benchmark" value={num(d.benchmark, 2)} sub={`${d.benchmark_kind.replace("_", " ")} of ${d.groups} groups`} />
            <Stat label="Best group" value={d.best_group} />
            <Stat label="Groups trailing" value={String(d.opportunities.length)} />
          </div>
          {d.opportunities.length > 0 && (
            <Section title="Ranked opportunities">
              <Table head={["Group", "Rows", "Average", "Gap per row", "Estimated gain", "What to do"]}
                rows={d.opportunities.map((o) => [o.group, o.rows.toLocaleString(), num(o.average, 2), num(o.gap_per_row, 2), <b key="g">{num(o.estimated_gain, 0)}</b>, <span key="a" className="text-xs text-muted">{o.action}</span>])} />
            </Section>
          )}
          {d.levers && (
            <Section title={`Levers for ${d.levers.y}`} note={d.levers.note}>
              <Table head={["Lever", "Effect per +1", "Effect of +10%", "Std. effect", ""]}
                rows={d.levers.items.map((l) => [l.lever, num(l.coef, 4), `${l.effect_of_plus_10pct > 0 ? "+" : ""}${num(l.effect_of_plus_10pct, 2)}`, l.std_coef == null ? "—" : num(l.std_coef, 2), <Badge key="b" tone={l.reliable ? "ok" : "muted"}>{l.reliable ? "reliable" : "unclear"}</Badge>])} />
              <p className="mt-2 text-xs text-muted">Model fit R² {pct(d.levers.r2, 0)}. A lever the model likes may still not work in practice; try it small first.</p>
            </Section>
          )}
        </>
      )}
    </div>
  );
}

