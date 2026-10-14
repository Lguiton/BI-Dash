"use client";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis, Legend } from "recharts";
import { money, moneyCompact, num } from "@/lib/format";
import { useChartColors } from "@/lib/useChartColors";
import type { HeatmapData, ScatterData } from "@/lib/types";

const CAT_VARS = ["var(--cat-1)", "var(--cat-2)", "var(--cat-3)", "var(--cat-4)", "var(--cat-5)", "var(--cat-6)"];

export function ScatterView({ data }: { data: ScatterData | null }) {
  const c = useChartColors();
  if (!data || !data.points.length) return <div className="flex h-72 items-center justify-center text-sm text-muted">No data for this selection</div>;
  const cats = [...new Set(data.points.map((p) => p.category))].sort();
  return (
    <div>
      <div className="h-72 w-full" role="img" aria-label={`Scatter plot of cost against revenue for ${num(data.points.length)} records, coloured by category.`}>
        <ResponsiveContainer width="100%" height="100%" minWidth={200}>
          <ScatterChart margin={{ top: 4, right: 8, bottom: 20, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
            <XAxis type="number" dataKey="cost" name="Cost" stroke={c.axis} fontSize={12} tickFormatter={moneyCompact}
                   label={{ value: "Operational cost", position: "insideBottom", offset: -8, fill: c.axis, fontSize: 12 }} />
            <YAxis type="number" dataKey="revenue" name="Revenue" stroke={c.axis} fontSize={12} tickFormatter={moneyCompact} width={48} />
            <ZAxis range={[24, 24]} />
            <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(v, n) => (n === "Cost" || n === "Revenue" ? money(Number(v)) : String(v))}
                     contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} />
            <Legend verticalAlign="top" height={28} />
            {cats.map((cat, i) => (
              <Scatter key={cat} name={cat} data={data.points.filter((p) => p.category === cat)} fill={CAT_VARS[i % CAT_VARS.length]} fillOpacity={0.55} isAnimationActive={false} />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      {data.sampled && <p className="mt-1 text-xs text-muted">Showing a repeatable sample of {num(data.points.length)} of {num(data.total)} records.</p>}
    </div>
  );
}

export function HeatmapView({ data }: { data: HeatmapData | null }) {
  if (!data || !data.cells.length) return <div className="flex h-72 items-center justify-center text-sm text-muted">No data for this selection</div>;
  const lookup = new Map(data.cells.map((c) => [`${c.entity_name}|${c.day}`, c]));
  const vals = data.cells.map((c) => c.avg_revenue);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const share = (v: number) => (hi === lo ? 50 : 8 + ((v - lo) / (hi - lo)) * 72); // 8%..80% accent mix
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] border-separate border-spacing-1 text-xs"
             aria-label="Heatmap of average revenue per record by entity and weekday">
        <thead>
          <tr>
            <th className="text-left font-normal text-muted" scope="col"><span className="sr-only">Entity</span></th>
            {data.days.map((d) => <th key={d} scope="col" className="font-normal text-muted">{d}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.entities.map((e) => (
            <tr key={e}>
              <th scope="row" className="whitespace-nowrap pr-2 text-left font-normal">{e}</th>
              {data.days.map((d) => {
                const cell = lookup.get(`${e}|${d}`);
                return (
                  <td key={d} className="rounded text-center tabular-nums"
                      title={cell ? `${e}, ${d}: ${money(cell.avg_revenue)} average over ${cell.records} record(s)` : `${e}, ${d}: no data`}
                      style={{ background: cell ? `color-mix(in srgb, var(--accent) ${share(cell.avg_revenue)}%, var(--panel))` : "var(--panel-2)", padding: "0.5rem 0.25rem" }}>
                    {cell ? Math.round(cell.avg_revenue).toLocaleString("en-US") : "·"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted">Average revenue per record. Darker means higher. Hover a cell for the record count.</p>
    </div>
  );
}
