"use client";
import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { Trash2 } from "lucide-react";
import { ApiError, deleteJson, getJson } from "@/lib/api";
import { num } from "@/lib/format";
import { useChartColors } from "@/lib/useChartColors";
import type { TableAggregate, TableBox, TableHistogram, TableProfile, TableScatter, UserTable } from "@/lib/types";

const CAT = ["var(--cat-1)", "var(--cat-2)", "var(--cat-3)", "var(--cat-4)", "var(--cat-5)", "var(--cat-6)"];
const KINDS = [["bar", "Bar"], ["line", "Line"], ["area", "Area"], ["pie", "Pie"], ["donut", "Donut"], ["histogram", "Histogram"], ["box", "Box plot"], ["scatter", "Scatter"]] as const;
type Kind = (typeof KINDS)[number][0];
const AGGS = [["sum", "Sum"], ["avg", "Average"], ["count", "Count of rows"], ["min", "Min"], ["max", "Max"], ["median", "Median"], ["distinct", "Distinct count"]] as const;
const BUCKETS = [["", "As is"], ["day", "Day"], ["week", "Week"], ["month", "Month"], ["quarter", "Quarter"], ["year", "Year"]] as const;

const fmt = (v: unknown) => (typeof v === "number" ? (Math.abs(v) >= 100 ? num(Math.round(v)) : String(Math.round(v * 100) / 100)) : v == null ? "—" : String(v));

export function TableExplorer({ table, onChanged }: { table: UserTable; onChanged: () => void }) {
  const c = useChartColors();
  const [profile, setProfile] = useState<TableProfile | null>(null);
  const [kind, setKind] = useState<Kind>("bar");
  const [x, setX] = useState("");
  const [y, setY] = useState("");
  const [agg, setAgg] = useState("sum");
  const [bucket, setBucket] = useState("month");
  const [group, setGroup] = useState("");
  const [data, setData] = useState<{ key: string; kind: Kind; value?: unknown; error?: string } | null>(null);
  const [confirmDel, setConfirmDel] = useState(false);

  const cols = profile?.columns ?? [];
  const nums = cols.filter((k) => k.kind === "number");
  const cats = cols.filter((k) => k.kind !== "number");
  const xOptions = kind === "histogram" || kind === "box" || kind === "scatter" ? nums : cols;
  const yOptions = agg === "distinct" || agg === "min" || agg === "max" ? cols : nums;
  // The pickers always show a valid column even if the stored choice does not fit the chart type (e.g. a text column for a histogram).
  const xe = xOptions.some((k) => k.name === x) ? x : (xOptions[0]?.name ?? "");
  const ye = yOptions.some((k) => k.name === y) ? y : (yOptions.find((k) => k.name !== xe)?.name ?? yOptions[0]?.name ?? "");
  const xCol = cols.find((k) => k.name === xe);

  useEffect(() => {
    const ctl = new AbortController();
    getJson<TableProfile>(`/api/data/tables/${table.table_name}/profile`, ctl.signal).then((p) => {
      setProfile(p);
      const firstCat = p.columns.find((k) => k.kind === "date") ?? p.columns.find((k) => k.kind === "text") ?? p.columns[0];
      const firstNum = p.columns.find((k) => k.kind === "number");
      setX(firstCat?.name ?? ""); setY(firstNum?.name ?? ""); setGroup(""); setKind(firstCat?.kind === "date" ? "line" : "bar");
      setData(null);
    }).catch(() => {});
    return () => ctl.abort();
  }, [table.table_name, table.rows_count]);

  const url = useMemo(() => {
    if (!xe) return null;
    const p = new URLSearchParams();
    const base = `/api/data/tables/${table.table_name}/chart?`;
    if (kind === "histogram") { p.set("kind", "histogram"); p.set("x", xe); p.set("bins", "20"); }
    else if (kind === "box") { p.set("kind", "box"); p.set("x", xe); if (group) p.set("by", group); }
    else if (kind === "scatter") { if (!ye) return null; p.set("kind", "scatter"); p.set("x", xe); p.set("y", ye); }
    else {
      p.set("kind", "aggregate"); p.set("x", xe); p.set("agg", agg); if (agg !== "count" && ye) p.set("y", ye);
      if (xCol?.kind === "date" && bucket) p.set("bucket", bucket);
      if (group && (kind === "bar" || kind === "line" || kind === "area")) p.set("group", group);
      p.set("limit", kind === "pie" || kind === "donut" ? "8" : "40");
    }
    return base + p.toString();
  }, [table.table_name, kind, xe, ye, agg, bucket, group, xCol?.kind]);

  useEffect(() => {
    if (!url) return;
    const ctl = new AbortController();
    getJson<unknown>(url, ctl.signal).then((value) => setData({ key: url, kind, value }))
      .catch((e) => { if (!ctl.signal.aborted) setData({ key: url, kind, error: e instanceof ApiError ? e.message : "Could not draw this chart." }); });
    return () => ctl.abort();
  }, [url, kind]);

  const sel = "field w-full";
  const need = (k: Kind): { y: boolean; group: boolean; agg: boolean } => ({
    y: !["histogram", "box"].includes(k) && !(["bar", "line", "area", "pie", "donut"].includes(k) && agg === "count"),
    group: ["bar", "line", "area", "box"].includes(k),
    agg: ["bar", "line", "area", "pie", "donut"].includes(k),
  });

  function draw() {
    if (!url) return <Msg text="Pick the columns to chart." />;
    if (!data || data.key !== url || data.kind !== kind) return <Msg text="Loading…" />;
    if (data.error) return <Msg text={data.error} />;
    const tip = { contentStyle: { backgroundColor: c.panel, borderColor: c.line, color: c.fg } };
    const axis = { stroke: c.axis, fontSize: 12 };
    if (kind === "histogram") {
      const h = data.value as TableHistogram;
      if (!h.bins.length) return <Msg text="No values in this column." />;
      return <Chart><BarChart data={h.bins}><CartesianGrid stroke={c.grid} vertical={false} /><XAxis dataKey="label" {...axis} /><YAxis {...axis} /><Tooltip {...tip} formatter={(v) => [num(Number(v)), "rows"]} labelFormatter={(l) => `from ${l}`} /><Bar dataKey="count" fill="var(--cat-1)" /></BarChart></Chart>;
    }
    if (kind === "scatter") {
      const s = data.value as TableScatter;
      return <><Chart><ScatterChart><CartesianGrid stroke={c.grid} /><XAxis type="number" dataKey="x" name={s.x} {...axis} /><YAxis type="number" dataKey="y" name={s.y} {...axis} /><Tooltip {...tip} cursor={{ strokeDasharray: "3 3" }} /><Scatter data={s.points} fill="var(--cat-1)" fillOpacity={0.6} /></ScatterChart></Chart>
        <p className="mt-1 text-xs text-muted">{num(s.n)} rows{s.shown < s.n ? ` (showing a random ${num(s.shown)})` : ""}. Correlation {s.correlation == null ? "n/a" : s.correlation.toFixed(2)}: close to 1 or −1 means the two move together; near 0 means no straight-line link.</p></>;
    }
    if (kind === "box") return <Box d={data.value as TableBox} colors={c} />;
    const a = data.value as TableAggregate;
    if (!a.data.length) return <Msg text="No data for this selection." />;
    if (kind === "pie" || kind === "donut") {
      const rows = a.data.map((r) => ({ name: String(r.x), value: Number(r.v ?? 0) })).filter((r) => r.value > 0);
      if (!rows.length) return <Msg text="Pie slices need positive values." />;
      return <Chart><PieChart><Pie data={rows} dataKey="value" nameKey="name" innerRadius={kind === "donut" ? "55%" : 0} outerRadius="80%" label={(e) => String(e.name)}>{rows.map((_, i) => <Cell key={i} fill={CAT[i % CAT.length]} />)}</Pie><Tooltip {...tip} /></PieChart></Chart>;
    }
    const series = a.series;
    const body = (S: typeof Bar | typeof Line | typeof Area) => series.map((s, i) => {
      const P = S as typeof Bar;
      return <P key={s} dataKey={s} name={s === "v" ? a.measure : s} fill={CAT[i % CAT.length]} stroke={CAT[i % CAT.length]} stackId={kind === "area" ? "a" : undefined} {...(kind === "line" ? { dot: false } : {})} />;
    });
    const parts = <><CartesianGrid stroke={c.grid} vertical={false} /><XAxis dataKey="x" {...axis} /><YAxis {...axis} tickFormatter={(v) => fmt(v)} /><Tooltip {...tip} formatter={(v) => fmt(v)} />{series.length > 1 && <Legend />}</>;
    return <Chart>{kind === "bar" ? <BarChart data={a.data}>{parts}{body(Bar)}</BarChart> : kind === "line" ? <LineChart data={a.data}>{parts}{body(Line)}</LineChart> : <AreaChart data={a.data}>{parts}{body(Area)}</AreaChart>}</Chart>;
  }

  async function remove() {
    try { await deleteJson(`/api/data/tables/${table.table_name}`); onChanged(); } catch { /* shown by reload */ }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-lg font-semibold">{table.table_name}</h3>
        <span className="text-sm text-muted">{num(table.rows_count)} rows · {table.columns.length} columns · from {table.source}</span>
        <span className="ml-auto" />
        {!confirmDel ? (
          <button className="btn" onClick={() => setConfirmDel(true)}><Trash2 className="h-4 w-4" aria-hidden /> Delete table</button>
        ) : (
          <span className="flex items-center gap-2 text-sm"><span style={{ color: "var(--bad)" }}>Delete permanently?</span>
            <button className="btn" style={{ color: "var(--bad)" }} onClick={remove}>Yes, delete</button>
            <button className="btn" onClick={() => setConfirmDel(false)}>Cancel</button></span>
        )}
      </div>

      <div className="card space-y-3 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <label className="text-xs text-muted">Chart
            <select className={sel} value={kind} onChange={(e) => setKind(e.target.value as Kind)}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
          <label className="text-xs text-muted">{kind === "histogram" || kind === "box" ? "Values" : "X (group by)"}
            <select className={sel} value={xe} onChange={(e) => setX(e.target.value)}>{xOptions.map((k) => <option key={k.name}>{k.name}</option>)}</select></label>
          {need(kind).agg && <label className="text-xs text-muted">Calculate
            <select className={sel} value={agg} onChange={(e) => setAgg(e.target.value)}>{AGGS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>}
          {need(kind).y && <label className="text-xs text-muted">{kind === "scatter" ? "Y" : "Of column"}
            <select className={sel} value={ye} onChange={(e) => setY(e.target.value)}>{yOptions.map((k) => <option key={k.name}>{k.name}</option>)}</select></label>}
          {xCol?.kind === "date" && need(kind).agg && <label className="text-xs text-muted">Dates by
            <select className={sel} value={bucket} onChange={(e) => setBucket(e.target.value)}>{BUCKETS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>}
          {need(kind).group && <label className="text-xs text-muted">{kind === "box" ? "Split by" : "Split into series"}
            <select className={sel} value={group} onChange={(e) => setGroup(e.target.value)}><option value="">None</option>{cats.map((k) => <option key={k.name}>{k.name}</option>)}</select></label>}
        </div>
        {nums.length === 0 && ["histogram", "box", "scatter"].includes(kind) && <p className="text-sm text-muted">This table has no numeric columns for that chart.</p>}
        <div className="min-h-[18rem]">{draw()}</div>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="px-4 pt-3 text-left text-xs uppercase tracking-wide text-muted">Column profile</caption>
          <thead><tr><th className="th">Column</th><th className="th">Type</th><th className="th">Missing</th><th className="th">Distinct</th><th className="th">Range / top values</th></tr></thead>
          <tbody>{cols.map((k) => (
            <tr key={k.name} className="border-t border-line">
              <td className="td font-medium">{k.name}</td><td className="td text-muted">{k.type.toLowerCase()}</td>
              <td className="td">{num(k.nulls)}</td><td className="td">{num(k.distinct_count)}</td>
              <td className="td">{k.kind === "number" ? `${fmt(k.min)} to ${fmt(k.max)} · avg ${fmt(k.mean)} · median ${fmt(k.median)}`
                : k.kind === "date" ? `${k.min} to ${k.max}` : k.top?.map((t) => `${t.value} (${num(t.n)})`).join(", ") ?? ""}</td>
            </tr>))}</tbody>
        </table>
      </div>
    </div>
  );
}

function Msg({ text }: { text: string }) { return <div className="flex h-64 items-center justify-center text-sm text-muted">{text}</div>; }
function Chart({ children }: { children: React.ReactElement }) { return <div className="h-72 w-full"><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>; }

/** Horizontal box plot in SVG: whiskers = min to max, box = middle 50%, bar = median. */
function Box({ d, colors }: { d: TableBox; colors: ReturnType<typeof useChartColors> }) {
  if (!d.boxes.length) return <Msg text="No values to plot." />;
  const lo = Math.min(...d.boxes.map((b) => b.mn)), hi = Math.max(...d.boxes.map((b) => b.mx));
  const W = 720, L = 120, R = 20, rowH = 38, top = 8, H = top + d.boxes.length * rowH + 28;
  const sx = (v: number) => L + ((v - lo) / (hi - lo || 1)) * (W - L - R);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Box plot of ${d.column}`}>
      {d.boxes.map((b, i) => {
        const cy = top + i * rowH + rowH / 2;
        return (
          <g key={b.name}>
            <text x={L - 8} y={cy + 4} textAnchor="end" fontSize="12" fill={colors.axis}>{b.name.slice(0, 16)}</text>
            <line x1={sx(b.mn)} x2={sx(b.mx)} y1={cy} y2={cy} stroke={colors.axis} />
            <rect x={sx(b.q1)} y={cy - 11} width={Math.max(2, sx(b.q3) - sx(b.q1))} height={22} fill={CAT[i % CAT.length]} fillOpacity={0.45} stroke={CAT[i % CAT.length]} />
            <line x1={sx(b.med)} x2={sx(b.med)} y1={cy - 11} y2={cy + 11} stroke={colors.fg} strokeWidth={2.5} />
            <title>{`${b.name}: n=${b.n}, min ${fmt(b.mn)}, Q1 ${fmt(b.q1)}, median ${fmt(b.med)}, Q3 ${fmt(b.q3)}, max ${fmt(b.mx)}`}</title>
          </g>
        );
      })}
      <text x={L} y={H - 8} fontSize="12" fill={colors.axis}>{fmt(lo)}</text>
      <text x={W - R} y={H - 8} fontSize="12" textAnchor="end" fill={colors.axis}>{fmt(hi)}</text>
    </svg>
  );
}
