"use client";
import { useEffect, useMemo, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Funnel, FunnelChart, LabelList, Legend, Line, Pie, PieChart,
  PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, Treemap, XAxis, YAxis, ZAxis,
} from "recharts";
import { ApiError, filterQuery, getJson } from "@/lib/api";
import { money, moneyCompact, num } from "@/lib/format";
import { useChartColors } from "@/lib/useChartColors";
import type { BubbleData, Breakdown, Distribution, FilterState } from "@/lib/types";

const CAT = ["var(--cat-1)", "var(--cat-2)", "var(--cat-3)", "var(--cat-4)", "var(--cat-5)", "var(--cat-6)"];
const color = (i: number) => CAT[i % CAT.length];

type Kind = "breakdown" | "distribution" | "bubble";
interface ChartDef { id: string; label: string; kind: Kind; group: string; hint: string; needsBy?: boolean; boxBy?: boolean }
const CHARTS: ChartDef[] = [
  { id: "pie", label: "Pie chart", kind: "breakdown", group: "Parts of a whole", needsBy: true, hint: "Share of the total. Best with 2 to 6 slices; use a bar when there are more." },
  { id: "donut", label: "Donut chart", kind: "breakdown", group: "Parts of a whole", needsBy: true, hint: "Like a pie, with the total in the middle." },
  { id: "treemap", label: "Treemap", kind: "breakdown", group: "Parts of a whole", needsBy: true, hint: "Area is the size of each group. Handles many groups better than a pie." },
  { id: "bar", label: "Ranked bar chart", kind: "breakdown", group: "Compare groups", needsBy: true, hint: "Groups sorted from biggest to smallest. The easiest chart to read accurately." },
  { id: "pareto", label: "Pareto chart", kind: "breakdown", group: "Compare groups", needsBy: true, hint: "Bars plus a cumulative line: which few groups make most of the total (the 80/20 rule)." },
  { id: "radar", label: "Radar chart", kind: "breakdown", group: "Compare groups", needsBy: true, hint: "Compares groups around a circle. Works for about 5 to 10 groups." },
  { id: "funnel", label: "Funnel chart", kind: "breakdown", group: "Compare groups", needsBy: true, hint: "Groups from largest to smallest as a funnel. Meant for stages that drop off." },
  { id: "area", label: "Stacked area (over time)", kind: "breakdown", group: "Over time", hint: "Monthly cost and profit stacked, so the top edge is revenue." },
  { id: "waterfall", label: "Waterfall (revenue to profit)", kind: "breakdown", group: "Over time", hint: "Starts at revenue, subtracts cost, ends at profit." },
  { id: "histogram", label: "Histogram", kind: "distribution", group: "Distribution", hint: "How per-record values are spread. Look for the shape, the centre and any second hump." },
  { id: "box", label: "Box plot", kind: "distribution", group: "Distribution", boxBy: true, hint: "Median, middle 50% (the box), whiskers and outlier dots, side by side for each group." },
  { id: "bubble", label: "Bubble chart", kind: "bubble", group: "Relationships", hint: "Each bubble is an entity: cost across, revenue up, size is units processed." },
];
const GROUPS = ["Parts of a whole", "Compare groups", "Over time", "Distribution", "Relationships"];
const BY_OPTS = [["category", "Category"], ["entity", "Entity"], ["status", "Status"], ["weekday", "Weekday"], ["month", "Month"]] as const;
const MEASURES = [["revenue", "Revenue"], ["cost", "Operational cost"], ["profit", "Profit"], ["units", "Units processed"], ["duration", "Duration"]] as const;

function Empty({ text }: { text: string }) {
  return <div className="flex h-72 items-center justify-center text-sm text-muted">{text}</div>;
}

export function ChartGallery({ filters, refreshKey }: { filters: FilterState; refreshKey: number }) {
  const c = useChartColors();
  const [chartId, setChartId] = useState("donut");
  const [by, setBy] = useState<string>("category");
  const [boxBy, setBoxBy] = useState<string>("category");
  const [measure, setMeasure] = useState<string>("revenue");
  const [bins, setBins] = useState(20);
  const def = CHARTS.find((x) => x.id === chartId)!;
  const [state, setState] = useState<{ key: string; kind: Kind; data?: unknown; error?: string } | null>(null);

  const url = useMemo(() => {
    if (def.kind === "bubble") return `/api/charts/bubble${filterQuery(filters)}`;
    if (def.kind === "distribution") return `/api/charts/distribution${filterQuery(filters, { measure, by: def.id === "box" ? boxBy : "none", bins })}`;
    const useBy = def.id === "area" ? "month" : def.id === "waterfall" ? "category" : by;
    return `/api/charts/breakdown${filterQuery(filters, { measure: def.id === "area" || def.id === "waterfall" ? "profit" : measure, by: useBy })}`;
  }, [def, filters, measure, by, boxBy, bins]);
  const key = `${url}|${refreshKey}`;

  useEffect(() => {
    const ctl = new AbortController();
    getJson<unknown>(url, ctl.signal)
      .then((data) => setState({ key, kind: def.kind, data }))
      .catch((e) => { if (!ctl.signal.aborted) setState({ key, kind: def.kind, error: e instanceof ApiError ? e.message : "Could not load this chart." }); });
    return () => ctl.abort();
  }, [url, key, def.kind]);

  const fresh = state?.key === key;
  const data = state?.data;
  const fmt = (v: number, kind?: string) => (kind === "number" ? num(Math.round(v)) : money(v));
  const compact = (v: number, kind?: string) => (kind === "number" ? (Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(Math.round(v))) : moneyCompact(v));
  const tip = { contentStyle: { backgroundColor: c.panel, borderColor: c.line, color: c.fg } };

  function body() {
    // Data from a different kind of chart (say bubble rows after switching to a pie) has the wrong shape: never draw it.
    if (!state || state.kind !== def.kind) return <Empty text="Loading…" />;
    if (state.error && fresh) return <Empty text={state.error} />;
    if (!data) return <Empty text="Loading…" />;

    if (def.kind === "breakdown") {
      const b = data as Breakdown;
      if (!b.rows?.length) return <Empty text="No data for this selection" />;
      const rows = b.rows;
      const kind = b.format;
      const aria = `${def.label} of ${b.measure_label.toLowerCase()} by ${b.by_label.toLowerCase()}, ${rows.length} groups.`;
      const wrap = (child: React.ReactElement, h = "h-80") => (
        <div className={`${h} w-full`} role="img" aria-label={aria}><ResponsiveContainer width="100%" height="100%" minWidth={200}>{child}</ResponsiveContainer></div>
      );
      if (def.id === "pie" || def.id === "donut") {
        const pos = rows.filter((r) => r.value > 0);
        if (!pos.length) return <Empty text="Every value is zero or negative, so there are no slices to draw." />;
        const total = pos.reduce((s, r) => s + r.value, 0);
        return (
          <div>
            {wrap(
              <PieChart>
                <Pie data={pos} dataKey="value" nameKey="name" innerRadius={def.id === "donut" ? "58%" : 0} outerRadius="85%" paddingAngle={def.id === "donut" ? 2 : 0}
                     stroke={c.panel} isAnimationActive={false} label={pos.length <= 8 ? ({ name, percent }: { name?: string; percent?: number }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%` : false}>
                  {pos.map((_, i) => <Cell key={i} fill={color(i)} />)}
                </Pie>
                <Tooltip {...tip} formatter={(v) => [`${fmt(Number(v), kind)} (${((Number(v) / total) * 100).toFixed(1)}%)`, b.measure_label]} />
                {pos.length > 8 && <Legend />}
              </PieChart>,
            )}
            {def.id === "donut" && <p className="-mt-1 text-center text-xs text-muted">Total {b.measure_label.toLowerCase()}: <strong className="text-fg">{fmt(total, kind)}</strong></p>}
            {pos.length < rows.length && <p className="mt-1 text-xs text-muted">Groups with a zero or negative total are left out; a pie can only show positive parts.</p>}
          </div>
        );
      }
      if (def.id === "treemap") {
        const pos = rows.filter((r) => r.value > 0).map((r, i) => ({ ...r, fill: color(i) }));
        if (!pos.length) return <Empty text="No positive values to size the boxes." />;
        return wrap(
          <Treemap data={pos} dataKey="value" nameKey="name" stroke={c.panel} isAnimationActive={false}
                   content={<TreeCell fmt={(v) => compact(v, kind)} />}>
            <Tooltip {...tip} formatter={(v) => [fmt(Number(v), kind), b.measure_label]} />
          </Treemap>,
        );
      }
      if (def.id === "bar") {
        const sorted = [...rows].sort((a, z) => z.value - a.value);
        return wrap(
          <BarChart data={sorted} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={c.grid} horizontal={false} />
            <XAxis type="number" stroke={c.axis} fontSize={11} tickFormatter={(v: number) => compact(v, kind)} />
            <YAxis type="category" dataKey="name" stroke={c.axis} fontSize={11} width={110} interval={0} />
            <Tooltip {...tip} formatter={(v) => [fmt(Number(v), kind), b.measure_label]} />
            <Bar dataKey="value" fill={c.revenue} radius={[0, 3, 3, 0]} isAnimationActive={false} />
          </BarChart>, sorted.length > 10 ? "h-[28rem]" : "h-80",
        );
      }
      if (def.id === "pareto") {
        const sorted = [...rows].filter((r) => r.value > 0).sort((a, z) => z.value - a.value);
        const total = sorted.reduce((s, r) => s + r.value, 0);
        let run = 0;
        const p = sorted.map((r) => ({ ...r, cum: total ? ((run += r.value) / total) * 100 : 0 }));
        const k80 = p.findIndex((r) => r.cum >= 80) + 1;
        return (
          <div>
            {wrap(
              <ComposedChart data={p} margin={{ top: 4, right: 8, bottom: 28, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
                <XAxis dataKey="name" stroke={c.axis} fontSize={11} interval={0} angle={-30} textAnchor="end" height={56} />
                <YAxis yAxisId="l" stroke={c.axis} fontSize={11} width={52} tickFormatter={(v: number) => compact(v, kind)} />
                <YAxis yAxisId="r" orientation="right" stroke={c.axis} fontSize={11} width={40} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
                <Tooltip {...tip} formatter={(v, n) => [n === "cum" ? `${Number(v).toFixed(1)}%` : fmt(Number(v), kind), n === "cum" ? "Cumulative share" : b.measure_label]} />
                <Bar yAxisId="l" dataKey="value" fill={c.revenue} radius={[3, 3, 0, 0]} isAnimationActive={false} />
                <Line yAxisId="r" dataKey="cum" stroke={color(1)} strokeWidth={2} dot isAnimationActive={false} />
              </ComposedChart>,
            )}
            {k80 > 0 && <p className="mt-1 text-xs text-muted">The top {k80} of {p.length} groups make up 80% of the total.</p>}
          </div>
        );
      }
      if (def.id === "radar") {
        const top = [...rows].sort((a, z) => z.value - a.value).slice(0, 10);
        return wrap(
          <RadarChart data={top} outerRadius="75%">
            <PolarGrid stroke={c.grid} />
            <PolarAngleAxis dataKey="name" tick={{ fill: c.axis, fontSize: 11 }} />
            <PolarRadiusAxis tick={{ fill: c.axis, fontSize: 10 }} tickFormatter={(v: number) => compact(v, kind)} />
            <Radar dataKey="value" stroke={c.revenue} fill={c.revenue} fillOpacity={0.35} isAnimationActive={false} />
            <Tooltip {...tip} formatter={(v) => [fmt(Number(v), kind), b.measure_label]} />
          </RadarChart>,
        );
      }
      if (def.id === "funnel") {
        const pos = [...rows].filter((r) => r.value > 0).sort((a, z) => z.value - a.value).map((r, i) => ({ ...r, fill: color(i) }));
        if (!pos.length) return <Empty text="No positive values for a funnel." />;
        return wrap(
          <FunnelChart>
            <Tooltip {...tip} formatter={(v) => [fmt(Number(v), kind), b.measure_label]} />
            <Funnel dataKey="value" nameKey="name" data={pos} isAnimationActive={false}>
              <LabelList position="right" fill={c.fg} stroke="none" dataKey="name" fontSize={11} />
            </Funnel>
          </FunnelChart>,
        );
      }
      if (def.id === "area") {
        const m = rows.map((r) => ({ name: r.name, Cost: r.cost, Profit: Math.round((r.revenue - r.cost) * 100) / 100 }));
        if (m.length < 2) return <Empty text="Needs at least two months of data." />;
        return wrap(
          <AreaChart data={m} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
            <XAxis dataKey="name" stroke={c.axis} fontSize={11} />
            <YAxis stroke={c.axis} fontSize={11} width={52} tickFormatter={moneyCompact} />
            <Tooltip {...tip} formatter={(v) => money(Number(v))} />
            <Legend />
            <Area type="monotone" dataKey="Cost" stackId="1" stroke={c.cost} fill={c.cost} fillOpacity={0.5} isAnimationActive={false} />
            <Area type="monotone" dataKey="Profit" stackId="1" stroke={c.profit} fill={c.profit} fillOpacity={0.5} isAnimationActive={false} />
          </AreaChart>,
        );
      }
      // waterfall
      const rev = rows.reduce((s, r) => s + r.revenue, 0), cost = rows.reduce((s, r) => s + r.cost, 0);
      const w = [
        { name: "Revenue", base: 0, v: rev, fill: c.revenue },
        { name: "Operational cost", base: Math.max(rev - cost, 0), v: Math.min(cost, rev), fill: c.cost },
        { name: "Profit", base: 0, v: Math.max(rev - cost, 0), fill: c.profit },
      ];
      return (
        <div>
          {wrap(
            <BarChart data={w} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
              <XAxis dataKey="name" stroke={c.axis} fontSize={12} />
              <YAxis stroke={c.axis} fontSize={11} width={52} tickFormatter={moneyCompact} />
              <Tooltip {...tip} formatter={(v, n) => (n === "base" ? [null, null] as never : [money(Number(v)), "Amount"])} />
              <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
              <Bar dataKey="v" stackId="w" isAnimationActive={false} radius={[3, 3, 0, 0]}>{w.map((r, i) => <Cell key={i} fill={r.fill} />)}</Bar>
            </BarChart>,
          )}
          <p className="mt-1 text-xs text-muted">Revenue {money(rev)} minus cost {money(cost)} = profit {money(rev - cost)}.</p>
        </div>
      );
    }

    if (def.kind === "distribution") {
      const d = data as Distribution;
      if (!d.count) return <Empty text="No data for this selection" />;
      if (def.id === "histogram") {
        const h = d.histogram.map((x) => ({ ...x, label: compact((x.from + x.to) / 2, d.format) }));
        return (
          <div>
            <div className="h-80 w-full" role="img" aria-label={`Histogram of ${d.measure_label.toLowerCase()} per record across ${d.count} records.`}>
              <ResponsiveContainer width="100%" height="100%" minWidth={200}>
                <BarChart data={h} barCategoryGap={1} margin={{ top: 4, right: 8, bottom: 16, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
                  <XAxis dataKey="label" stroke={c.axis} fontSize={11} interval="preserveStartEnd" label={{ value: `${d.measure_label} per record`, position: "insideBottom", offset: -10, fill: c.axis, fontSize: 12 }} />
                  <YAxis stroke={c.axis} fontSize={11} width={44} allowDecimals={false} />
                  <Tooltip {...tip} labelFormatter={(_, p) => { const r = p?.[0]?.payload; return r ? `${fmt(r.from, d.format)} to ${fmt(r.to, d.format)}` : ""; }} formatter={(v) => [num(Number(v)), "Records"]} />
                  <Bar dataKey="count" fill={c.revenue} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-1 text-xs text-muted">{num(d.count)} records in {d.bins} equal-width bins. Change the bin count to see how the shape depends on it.</p>
          </div>
        );
      }
      return <BoxPlot d={d} fmt={compact} full={fmt} colors={c} />;
    }

    const bd = data as BubbleData;
    if (!bd.rows?.length) return <Empty text="No data for this selection" />;
    const cats = [...new Set(bd.rows.map((r) => r.category))].sort();
    return (
      <div className="h-80 w-full" role="img" aria-label={`Bubble chart of ${bd.rows.length} entities: cost, revenue and units.`}>
        <ResponsiveContainer width="100%" height="100%" minWidth={200}>
          <ScatterChart margin={{ top: 4, right: 12, bottom: 20, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
            <XAxis type="number" dataKey="cost" name="Cost" stroke={c.axis} fontSize={11} tickFormatter={moneyCompact} label={{ value: "Total cost", position: "insideBottom", offset: -8, fill: c.axis, fontSize: 12 }} />
            <YAxis type="number" dataKey="revenue" name="Revenue" stroke={c.axis} fontSize={11} tickFormatter={moneyCompact} width={52} />
            <ZAxis type="number" dataKey="units" name="Units" range={[60, 600]} />
            <Tooltip {...tip} cursor={{ strokeDasharray: "3 3" }} formatter={(v, n) => (n === "Units" ? num(Number(v)) : money(Number(v)))} labelFormatter={() => ""} />
            <Legend verticalAlign="top" height={28} />
            {cats.map((cat, i) => <Scatter key={cat} name={cat} data={bd.rows.filter((r) => r.category === cat)} fill={color(i)} fillOpacity={0.6} isAnimationActive={false} />)}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    );
  }

  const selectCls = "rounded-md border border-line bg-panel px-2 py-1.5 text-sm";
  const showMeasure = !["area", "waterfall", "bubble"].includes(def.id);
  return (
    <div className="card p-5">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide">Chart gallery</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-muted">Chart
            <select className={`${selectCls} mt-0.5 block`} value={chartId} onChange={(e) => setChartId(e.target.value)}>
              {GROUPS.map((g) => (
                <optgroup key={g} label={g}>
                  {CHARTS.filter((x) => x.group === g).map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          {showMeasure && (
            <label className="text-xs text-muted">Measure
              <select className={`${selectCls} mt-0.5 block`} value={measure} onChange={(e) => setMeasure(e.target.value)}>
                {MEASURES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
          )}
          {def.needsBy && (
            <label className="text-xs text-muted">Group by
              <select className={`${selectCls} mt-0.5 block`} value={by} onChange={(e) => setBy(e.target.value)}>
                {BY_OPTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
          )}
          {def.boxBy && (
            <label className="text-xs text-muted">Compare by
              <select className={`${selectCls} mt-0.5 block`} value={boxBy} onChange={(e) => setBoxBy(e.target.value)}>
                <option value="none">All records</option><option value="category">Category</option><option value="entity">Entity</option><option value="status">Status</option>
              </select>
            </label>
          )}
          {def.id === "histogram" && (
            <label className="text-xs text-muted">Bins
              <select className={`${selectCls} mt-0.5 block`} value={bins} onChange={(e) => setBins(Number(e.target.value))}>
                {[10, 20, 30, 40].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          )}
        </div>
      </div>
      <p className="mb-2 text-xs text-muted">{def.hint} Uses the filters above.</p>
      <div className={fresh ? "" : "opacity-60 transition-opacity"}>{body()}</div>
    </div>
  );
}

interface TreeProps { x?: number; y?: number; width?: number; height?: number; name?: string; value?: number; fill?: string; fmt: (v: number) => string }
function TreeCell({ x = 0, y = 0, width = 0, height = 0, name, value, fill, fmt }: TreeProps) {
  if (width < 2 || height < 2) return null;
  const big = width > 70 && height > 36;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={fill} fillOpacity={0.85} stroke="var(--panel)" strokeWidth={2} rx={3} />
      {big && <text x={x + 8} y={y + 18} fill="#fff" fontSize={12} fontWeight={600}>{name}</text>}
      {big && value != null && <text x={x + 8} y={y + 34} fill="#fff" fontSize={11} opacity={0.9}>{fmt(value)}</text>}
    </g>
  );
}

/** Horizontal box plot drawn directly in SVG: box = middle 50%, line = median, whiskers = last point within 1.5 x IQR, dots = outliers. */
function BoxPlot({ d, fmt, full, colors }: { d: Distribution; fmt: (v: number, k?: string) => string; full: (v: number, k?: string) => string; colors: ReturnType<typeof useChartColors> }) {
  const boxes = d.boxes;
  const [hover, setHover] = useState<string | null>(null);
  if (!boxes.length) return <Empty text="No data for this selection" />;
  const lo = Math.min(...boxes.flatMap((b) => [b.whisker_low, ...b.outliers]));
  const hi = Math.max(...boxes.flatMap((b) => [b.whisker_high, ...b.outliers]));
  const pad = (hi - lo || 1) * 0.04;
  const W = 640, left = 120, right = 16, rowH = 46, top = 8, axisH = 28;
  const H = top + boxes.length * rowH + axisH;
  const sx = (v: number) => left + ((v - (lo - pad)) / (hi - lo + 2 * pad)) * (W - left - right);
  const ticks = Array.from({ length: 6 }, (_, i) => lo + ((hi - lo) * i) / 5);
  const hb = boxes.find((b) => b.name === hover);
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Box plot of ${d.measure_label.toLowerCase()} for ${boxes.length} group${boxes.length > 1 ? "s" : ""}.`}>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={sx(t)} x2={sx(t)} y1={top} y2={H - axisH} stroke={colors.grid} strokeDasharray="3 3" />
            <text x={sx(t)} y={H - 10} textAnchor="middle" fontSize={11} fill={colors.axis}>{fmt(t, d.format)}</text>
          </g>
        ))}
        {boxes.map((b, i) => {
          const cy = top + i * rowH + rowH / 2, col = color(i), h = 22;
          return (
            <g key={b.name} onMouseEnter={() => setHover(b.name)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(b.name)} onBlur={() => setHover(null)} tabIndex={0}>
              <title>{`${b.name}: median ${full(b.median, d.format)}, middle half ${full(b.q1, d.format)} to ${full(b.q3, d.format)}, ${b.outlier_count} outliers`}</title>
              <text x={left - 8} y={cy + 4} textAnchor="end" fontSize={11} fill={colors.fg}>{b.name.length > 16 ? `${b.name.slice(0, 15)}…` : b.name}</text>
              <line x1={sx(b.whisker_low)} x2={sx(b.q1)} y1={cy} y2={cy} stroke={col} strokeWidth={2} />
              <line x1={sx(b.q3)} x2={sx(b.whisker_high)} y1={cy} y2={cy} stroke={col} strokeWidth={2} />
              <line x1={sx(b.whisker_low)} x2={sx(b.whisker_low)} y1={cy - 6} y2={cy + 6} stroke={col} strokeWidth={2} />
              <line x1={sx(b.whisker_high)} x2={sx(b.whisker_high)} y1={cy - 6} y2={cy + 6} stroke={col} strokeWidth={2} />
              <rect x={sx(b.q1)} y={cy - h / 2} width={Math.max(sx(b.q3) - sx(b.q1), 1)} height={h} fill={col} fillOpacity={0.35} stroke={col} strokeWidth={2} rx={2} />
              <line x1={sx(b.median)} x2={sx(b.median)} y1={cy - h / 2} y2={cy + h / 2} stroke={colors.fg} strokeWidth={2.5} />
              {b.outliers.map((o, j) => <circle key={j} cx={sx(o)} cy={cy} r={3} fill="none" stroke={col} strokeWidth={1.5} />)}
            </g>
          );
        })}
      </svg>
      <p className="mt-1 text-xs text-muted">
        {hb
          ? `${hb.name}: n=${num(hb.n)}, median ${full(hb.median, d.format)}, mean ${full(hb.mean, d.format)}, box ${full(hb.q1, d.format)} to ${full(hb.q3, d.format)}, ${hb.outlier_count} outlier${hb.outlier_count === 1 ? "" : "s"}.`
          : "The box holds the middle half of records; the dark line is the median; dots are outliers (more than 1.5 box-widths beyond the box). Hover a row for the numbers."}
      </p>
    </div>
  );
}
