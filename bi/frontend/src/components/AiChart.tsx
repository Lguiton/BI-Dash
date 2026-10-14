"use client";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useChartColors } from "@/lib/useChartColors";
import type { AiChart as Chart } from "@/lib/types";

/** Renders a chart the AI agent asked for. The data comes from a read-only SQL query the user can inspect. */
export function AiChart({ chart }: { chart: Chart }) {
  const c = useChartColors();
  const many = chart.points.length > 12;
  const common = { data: chart.points, margin: { top: 4, right: 8, bottom: many ? 28 : 8, left: 0 } };
  const axes = (
    <>
      <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
      <XAxis dataKey="x" stroke={c.axis} fontSize={11} interval="preserveStartEnd" angle={many ? -35 : 0} textAnchor={many ? "end" : "middle"} height={many ? 50 : 30} />
      <YAxis stroke={c.axis} fontSize={11} width={52} tickFormatter={(v: number) => Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v)} />
      <Tooltip contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} formatter={(v) => [Number(v).toLocaleString(), chart.y_label]} />
    </>
  );
  return (
    <figure className="space-y-1">
      <figcaption className="text-sm font-semibold">{chart.title || `${chart.y_label} by ${chart.x_label}`}</figcaption>
      <div className="h-64 w-full" role="img" aria-label={`${chart.kind} chart: ${chart.title}. ${chart.points.length} points.`}>
        <ResponsiveContainer width="100%" height="100%" minWidth={200}>
          {chart.kind === "line" ? (
            <LineChart {...common}>{axes}<Line type="monotone" dataKey="y" stroke={c.revenue} strokeWidth={2} dot={chart.points.length < 20} /></LineChart>
          ) : (
            <BarChart {...common}>{axes}<Bar dataKey="y" fill={c.revenue} radius={[3, 3, 0, 0]} /></BarChart>
          )}
        </ResponsiveContainer>
      </div>
      {chart.truncated && <p className="text-xs text-muted">Showing the first {chart.points.length} points.</p>}
    </figure>
  );
}
