"use client";
import { Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { money, moneyCompact } from "@/lib/format";
import { useChartColors } from "@/lib/useChartColors";
import type { EntityRow, ForecastPoint, TrendPoint } from "@/lib/types";

function Empty({ text }: { text: string }) {
  return <div className="flex h-full items-center justify-center text-sm text-muted">{text}</div>;
}

const FORECAST_HISTORY_DAYS = 90;

export function TrendChart({ data: fullData, forecast }: { data: TrendPoint[]; forecast?: ForecastPoint[] }) {
  const c = useChartColors();
  if (!fullData.length) return <Empty text="No data for this selection" />;
  const showF = !!forecast?.length;
  // With a forecast on, zoom to the recent past so the next two weeks stay readable.
  const data = showF && fullData.length > FORECAST_HISTORY_DAYS ? fullData.slice(-FORECAST_HISTORY_DAYS) : fullData;
  type Row = Partial<TrendPoint> & { date: string; forecast?: number; band?: [number, number] };
  const rows: Row[] = [
    ...data,
    ...(showF ? forecast!.map((f) => ({ date: f.date, forecast: f.forecast, band: [f.lower, f.upper] as [number, number] })) : []),
  ];
  // The forecast line starts at the last real revenue point, so the two lines join up visually.
  if (showF) rows[data.length - 1] = { ...rows[data.length - 1], forecast: data[data.length - 1].revenue };
  const label = `Line chart of daily revenue, cost and profit across ${data.length} days, from ${data[0].date} to ${data[data.length - 1].date}.` +
    (showF ? ` A dashed line forecasts revenue for the next ${forecast!.length} days with a shaded 95 percent range.` : "");
  const dots = data.length < 15;
  const zoomed = data.length < fullData.length;
  return (
    <div className="w-full" role="img" aria-label={label}>
      {zoomed && <p className="mb-1 text-xs text-muted">Showing the last {FORECAST_HISTORY_DAYS} days so the forecast is readable. Untick the forecast to see everything.</p>}
      <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%" minWidth={200}>
        <ComposedChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
          <XAxis dataKey="date" stroke={c.axis} fontSize={12} tickFormatter={(d: string) => d.slice(5)} />
          <YAxis stroke={c.axis} fontSize={12} tickFormatter={moneyCompact} width={48} />
          <Tooltip formatter={(v) => (Array.isArray(v) ? `${money(Number(v[0]))} to ${money(Number(v[1]))}` : money(Number(v)))}
                   contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} />
          <Legend />
          {showF && <Area dataKey="band" name="95% range" stroke="none" fill={c.revenue} fillOpacity={0.15} legendType="square" />}
          <Line type="monotone" dataKey="revenue" stroke={c.revenue} strokeWidth={2} name="Revenue" dot={dots} />
          <Line type="monotone" dataKey="cost" stroke={c.cost} strokeWidth={2} name="Cost" dot={dots} />
          <Line type="monotone" dataKey="profit" stroke={c.profit} strokeWidth={2} name="Profit" dot={dots} />
          {showF && <Line type="monotone" dataKey="forecast" stroke={c.revenue} strokeWidth={2} strokeDasharray="6 4" name="Revenue forecast" dot={false} />}
        </ComposedChart>
      </ResponsiveContainer>
      </div>
    </div>
  );
}

interface EntityChartProps {
  data: EntityRow[];
  selectedId: string;
  onSelect: (entityId: string) => void;
}

export function EntityChart({ data, selectedId, onSelect }: EntityChartProps) {
  const c = useChartColors();
  if (!data.length) return <Empty text="No data for this selection" />;
  const label = `Bar chart of revenue and profit for ${data.length} entities. Select a bar to filter the dashboard to that entity.`;
  const pick = (entry: unknown) => {
    const id = (entry as { payload?: { entity_id?: string } })?.payload?.entity_id;
    if (id) onSelect(id === selectedId ? "" : id);
  };
  return (
    <div className="h-64 w-full" role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height="100%" minWidth={200}>
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
          <XAxis dataKey="entity_name" stroke={c.axis} fontSize={11} interval={0} angle={-35} textAnchor="end" height={data.length > 5 ? 76 : 30}
                 tickFormatter={(s: string) => (s.length > 16 ? `${s.slice(0, 15)}…` : s)} />
          <YAxis stroke={c.axis} fontSize={12} tickFormatter={moneyCompact} width={48} />
          <Tooltip formatter={(v) => money(Number(v))} cursor={{ fill: c.grid }} contentStyle={{ backgroundColor: c.panel, borderColor: c.line, color: c.fg }} />
          <Legend />
          <Bar dataKey="revenue" name="Revenue" fill={c.revenue} radius={[4, 4, 0, 0]} onClick={pick} cursor="pointer">
            {data.map((d) => <Cell key={d.entity_id} fill={c.revenue} fillOpacity={!selectedId || selectedId === d.entity_id ? 1 : 0.35} />)}
          </Bar>
          <Bar dataKey="profit" name="Profit" fill={c.profit} radius={[4, 4, 0, 0]} onClick={pick} cursor="pointer">
            {data.map((d) => <Cell key={d.entity_id} fill={c.profit} fillOpacity={!selectedId || selectedId === d.entity_id ? 1 : 0.35} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
