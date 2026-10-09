"use client";

import { Activity, DollarSign, Layers, Percent, RefreshCw, TrendingUp } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Filters } from "@/components/Filters";
import { EntityChart, TrendChart } from "@/components/Charts";
import { DatasetCard } from "@/components/DatasetCard";
import { ChartGallery } from "@/components/ChartGallery";
import { EntityTable } from "@/components/EntityTable";
import { HeatmapView, ScatterView } from "@/components/ExplorePanel";
import { ErrorBanner } from "@/components/ErrorBanner";
import { InsightsPanel } from "@/components/InsightsPanel";
import { KpiCard } from "@/components/KpiCard";
import { NavBar } from "@/components/NavBar";
import { RecordsPanel } from "@/components/RecordsPanel";
import { CompanyCard } from "@/components/CompanyCard";
import { StudyWidget } from "@/components/StudyWidget";
import { ReportButtons } from "@/components/ReportButtons";
import { ThemeToggle } from "@/components/ThemeToggle";
import { RealBanner, WorkspaceSwitcher } from "@/components/WorkspaceSwitcher";
import { UploadPanel } from "@/components/UploadPanel";
import { ApiError, filterQuery, getJson } from "@/lib/api";
import { money, num, pct } from "@/lib/format";
import {
  EMPTY_FILTERS, type EntityRow, type FilterState, type Forecast, type HeatmapData, type Insight, type Meta,
  type ScatterData, type Summary, type TrendPoint,
} from "@/lib/types";

export default function Dashboard() {
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [data, setData] = useState<{
    key: string;
    summary?: Summary; trend?: TrendPoint[]; entities?: EntityRow[]; insights?: Insight[];
    forecast?: Forecast; scatter?: ScatterData; heatmap?: HeatmapData; error?: string;
  } | null>(null);
  const [showForecast, setShowForecast] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((n) => n + 1), []);
  const requestKey = `${filterQuery(filters)}|${refreshKey}`;

  // Filter options + data range. Reloaded on refresh (e.g. after an import).
  useEffect(() => {
    const ctl = new AbortController();
    getJson<Meta>("/api/analytics/meta", ctl.signal).then(setMeta).catch(() => { /* surfaced by the data load below */ });
    return () => ctl.abort();
  }, [refreshKey]);

  // Main analytics load. A newer request aborts the older one, so a slow
  // response can never overwrite fresher data.
  useEffect(() => {
    const ctl = new AbortController();
    const q = filterQuery(filters);
    Promise.all([
      getJson<Summary>(`/api/analytics/summary${q}`, ctl.signal),
      getJson<TrendPoint[]>(`/api/analytics/timeseries${q}`, ctl.signal),
      getJson<EntityRow[]>(`/api/analytics/by-entity${q}`, ctl.signal),
      getJson<{ insights: Insight[] }>(`/api/analytics/insights${q}`, ctl.signal),
      getJson<Forecast>(`/api/analytics/forecast${q}`, ctl.signal),
      getJson<ScatterData>(`/api/analytics/scatter${q}`, ctl.signal),
      getJson<HeatmapData>(`/api/analytics/heatmap${q}`, ctl.signal),
    ])
      .then(([summary, trend, entities, i, forecast, scatter, heatmap]) =>
        setData({ key: requestKey, summary, trend, entities, insights: i.insights, forecast, scatter, heatmap }))
      .catch((err) => {
        if (ctl.signal.aborted) return;
        setData((prev) => ({ ...prev, key: requestKey, error: err instanceof ApiError ? err.message : "Something went wrong loading analytics." }));
      });
    return () => ctl.abort();
  }, [filters, refreshKey, requestKey]);

  // Last good data stays on screen (dimmed) while a newer request is in flight.
  const summary = data?.summary ?? null;
  const trend = useMemo(() => data?.trend ?? [], [data?.trend]);
  const entities = data?.entities ?? [];
  const insights = data?.insights ?? [];
  const forecast = data?.forecast;
  const forecastPoints = forecast?.available ? forecast.points : undefined;
  const loading = data?.key !== requestKey;
  const error = data?.key === requestKey ? data.error ?? null : null;

  const spark = useMemo(() => ({
    revenue: trend.map((t) => t.revenue),
    profit: trend.map((t) => t.profit),
    margin: trend.map((t) => (t.revenue ? (t.profit / t.revenue) * 100 : 0)),
    units: trend.map((t) => t.units),
  }), [trend]);

  const d = summary?.deltas;
  const empty = summary != null && summary.record_count === 0;

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Business Intelligence Dashboard</h1>
          <p className="text-sm text-muted">
            {meta?.min_date && meta.max_date
              ? `${num(meta.record_count)} records · ${meta.min_date} to ${meta.max_date}`
              : "FastAPI + DuckDB analytics engine"}
          </p>
        </div>
        <div className="flex flex-wrap items-start gap-2">
          <NavBar />
          <WorkspaceSwitcher />
          <ThemeToggle />
          <button className="btn" onClick={refresh} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden /> Refresh
          </button>
        </div>
      </header>

      <RealBanner />
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <ReportButtons filters={filters} />

      <CompanyCard />

      <StudyWidget />

      <UploadPanel onLoaded={() => { setFilters(EMPTY_FILTERS); refresh(); }} />

      <DatasetCard refreshKey={refreshKey} />

      <Filters meta={meta} filters={filters} onChange={setFilters} />

      {summary?.previous_range && (
        <p className="-mt-3 text-xs text-muted">
          Changes compare with the previous equal-length period ({summary.previous_range.date_from} to {summary.previous_range.date_to}).
        </p>
      )}

      {empty && !error && (
        <div className="card p-6 text-center text-sm text-muted">
          No records match these filters. Try widening the date range or resetting the filters.
        </div>
      )}

      <section aria-label="Key metrics" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Revenue" icon={<DollarSign className="h-4 w-4 text-[var(--c-revenue)]" />} loading={loading}
                 value={money(summary?.total_revenue)} caption={summary ? `Cost ${money(summary.total_cost)}` : ""}
                 delta={d?.total_revenue} spark={spark.revenue} sparkColor="var(--c-revenue)" />
        <KpiCard label="Net profit" icon={<TrendingUp className="h-4 w-4 text-[var(--c-profit)]" />} loading={loading}
                 value={money(summary?.net_profit)} caption="Revenue minus cost"
                 delta={d?.net_profit} spark={spark.profit} sparkColor="var(--c-profit)" />
        <KpiCard label="Net margin" icon={<Percent className="h-4 w-4 text-accent" />} loading={loading}
                 value={pct(summary?.net_margin_pct)} caption="Profit ÷ revenue"
                 delta={d?.net_margin_pct} deltaUnit=" pts" spark={spark.margin} />
        <KpiCard label="Units processed" icon={<Layers className="h-4 w-4 text-amber-500" />} loading={loading}
                 value={num(summary?.total_units)}
                 caption={summary?.rev_per_unit != null ? `${money(summary.rev_per_unit)} revenue / unit` : ""}
                 delta={d?.total_units} spark={spark.units} sparkColor="var(--muted)" />
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="card p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide">Revenue, cost and profit over time</h2>
              <label className="flex items-center gap-2 text-xs text-muted">
                <input type="checkbox" checked={showForecast} onChange={(e) => setShowForecast(e.target.checked)} disabled={!forecastPoints} />
                14-day forecast
              </label>
            </div>
            <TrendChart data={trend} forecast={showForecast ? forecastPoints : undefined} />
            {forecast && !forecast.available && <p className="mt-2 text-xs text-muted">{forecast.reason}</p>}
            {forecast?.available && showForecast && (
              <p className="mt-2 text-xs text-muted">
                {forecast.method}; shaded band is a 95% range.
                {forecast.backtest && ` Backtest error on the last ${forecast.backtest.days} days: ${forecast.backtest.mape_pct}%.`}
              </p>
            )}
          </div>
          <div className="card p-5">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide">
              <Activity className="h-4 w-4 text-accent" aria-hidden /> Revenue and profit by entity
            </h2>
            <EntityChart data={entities} selectedId={filters.entity_id} onSelect={(id) => setFilters({ ...filters, entity_id: id })} />
          </div>
          <ChartGallery filters={filters} refreshKey={refreshKey} />
        </div>
        <InsightsPanel insights={insights} loading={loading} />
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2" aria-label="More views">
        <div className="card p-5">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide">Cost vs revenue per record</h2>
          <p className="mb-3 text-xs text-muted">Each dot is one record. Dots far from the rest of their category are worth a look.</p>
          <ScatterView data={data?.scatter ?? null} />
        </div>
        <div className="card p-5">
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide">Revenue by weekday</h2>
          <p className="mb-3 text-xs text-muted">Which entities earn more on which days.</p>
          <HeatmapView data={data?.heatmap ?? null} />
        </div>
      </section>

      <EntityTable rows={entities} selectedId={filters.entity_id} onSelect={(id) => setFilters({ ...filters, entity_id: id })} />

      <RecordsPanel filters={filters} refreshKey={refreshKey} />
    </div>
  );
}
