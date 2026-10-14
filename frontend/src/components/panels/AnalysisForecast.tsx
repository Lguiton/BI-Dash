"use client";
import { useState } from "react";
import { CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, Area } from "recharts";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Field, Section, Stat, Table, num } from "./kit";
import { ColSelect, Lesson, Sentences, first, useRun, type Base, type Col } from "./analysisKit";

interface Arima {
  available: boolean; reason?: string; name: string; points: number; filled_gaps: number; note: string; lesson: string; sentences: string[];
  series: { t: string; v: number }[]; forecast: { t: string; v: number; low: number; high: number }[];
  backtest: { points: number; mae: number; naive_mae: number; better_than_naive: boolean; mape: number | null } | null;
}

export function ArimaTab({ base, cols }: { base: Base; cols: Col[] }) {
  const [dateCol, setDateCol] = useState(first(cols, "date"));
  const [agg, setAgg] = useState("sum");
  const [value, setValue] = useState(first(cols, "number"));
  const [bucket, setBucket] = useState("day");
  const [horizon, setHorizon] = useState(14);
  const [d, setD] = useState(1);
  const r = useRun<Arima>();
  const x = r.data && r.data.available ? r.data : null;
  const chart = x ? [...x.series.slice(-120).map((s) => ({ t: s.t, v: s.v })), ...x.forecast.map((f) => ({ t: f.t, fc: f.v, band: [f.low, f.high] as [number, number] }))] : [];
  return (
    <div className="space-y-4">
      <Section title="ARIMA-style forecast (the series' own past)">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
          <ColSelect label="Date column" value={dateCol} onChange={setDateCol} cols={cols} kinds={["date"]} />
          <Field label="Measure"><select className="field" value={agg} onChange={(e) => setAgg(e.target.value)}><option value="sum">Total</option><option value="avg">Average</option><option value="count">Number of rows</option><option value="min">Smallest</option><option value="max">Largest</option></select></Field>
          {agg !== "count" && <ColSelect label="Of this column" value={value} onChange={setValue} cols={cols} kinds={["number"]} />}
          <Field label="Group by"><select className="field" value={bucket} onChange={(e) => setBucket(e.target.value)}><option value="day">Day</option><option value="week">Week</option><option value="month">Month</option></select></Field>
          <Field label={`Look ahead (${bucket}s)`}><input className="field" type="number" min={1} max={60} value={horizon} onChange={(e) => setHorizon(Math.max(1, Math.min(60, Number(e.target.value) || 1)))} /></Field>
          <Field label="Differencing"><select className="field" value={d} onChange={(e) => setD(Number(e.target.value))}><option value={1}>1 (model the change)</option><option value={0}>0 (model the level)</option></select></Field>
        </div>
        <button className="btn btn-primary mt-3" disabled={r.busy || !dateCol || (agg !== "count" && !value)} onClick={() => r.run("/api/stats/arima", { ...base, date_col: dateCol, value_col: agg === "count" ? null : value, agg, bucket, horizon, d })}>{r.busy ? "Fitting…" : "Fit and forecast"}</button>
      </Section>
      {r.err && <ErrorBanner message={r.err} />}
      {r.data && !r.data.available && <p className="rounded border border-line p-3 text-sm">{r.data.reason}</p>}
      {x && (
        <>
          <Lesson text={x.lesson} />
          <Sentences items={x.sentences} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Model chosen" value={x.name} sub="picked by AIC" />
            <Stat label="Periods used" value={String(x.points)} sub={x.filled_gaps ? `${x.filled_gaps} gap(s) filled` : undefined} />
            <Stat label="Beats the simple guess?" value={x.backtest ? (x.backtest.better_than_naive ? "Yes" : "No") : "n/a"} sub={x.backtest ? `miss ${num(x.backtest.mae, 2)} vs ${num(x.backtest.naive_mae, 2)}` : undefined} />
          </div>
          <div className="card h-80 min-w-0 p-3" role="img" aria-label="Line chart of the measure with the ARIMA forecast and its 95 percent range">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chart} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                <XAxis dataKey="t" stroke="var(--muted)" fontSize={11} tickFormatter={(s: string) => s.slice(5)} minTickGap={24} />
                <YAxis stroke="var(--muted)" fontSize={11} width={56} tickFormatter={(s: number) => num(s, 0)} />
                <Tooltip />
                <Legend />
                <Area dataKey="band" name="95% range" stroke="none" fill="var(--accent)" fillOpacity={0.15} />
                <Line dataKey="v" name="Actual" stroke="var(--c-revenue)" strokeWidth={1.5} dot={false} connectNulls />
                <Line dataKey="fc" name="Forecast" stroke="var(--accent)" strokeWidth={2} strokeDasharray="6 4" dot={{ r: 2 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <Section title="Forecast table" note={x.note}>
            <Table head={["When", "Expected", "Low (95%)", "High (95%)"]} rows={x.forecast.map((f) => [f.t, num(f.v, 2), num(f.low, 2), num(f.high, 2)])} />
          </Section>
        </>
      )}
    </div>
  );
}
