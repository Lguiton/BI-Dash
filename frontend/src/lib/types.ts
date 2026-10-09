export interface Kpis {
  record_count: number;
  total_revenue: number;
  total_cost: number;
  net_profit: number;
  net_margin_pct: number | null;
  total_units: number;
  rev_per_unit: number | null;
  avg_duration_minutes: number | null;
}

export type Deltas = Record<
  "total_revenue" | "total_cost" | "net_profit" | "total_units" | "rev_per_unit" | "net_margin_pct",
  number | null
>;

export interface Summary extends Kpis {
  previous: Kpis | null;
  deltas: Deltas | null;
  previous_range: { date_from: string; date_to: string } | null;
}

export interface TrendPoint {
  date: string;
  revenue: number;
  cost: number;
  profit: number;
  units: number;
}

export interface EntityRow {
  entity_id: string;
  entity_name: string;
  category: string;
  revenue: number;
  profit: number;
  margin_pct: number;
  volume: number;
  records: number;
  avg_revenue_per_record: number;
  avg_cost_per_record: number;
  baseline_target: number | null;
  vs_baseline_pct: number | null;
}

export interface RecordRow {
  fact_id: string;
  record_date: string;
  entity_id: string;
  entity_name: string;
  category: string | null;
  revenue: number;
  operational_cost: number;
  profit: number;
  units_processed: number;
  duration_minutes: number | null;
  status: string | null;
}

export interface RecordsPage {
  total: number;
  limit: number;
  offset: number;
  rows: RecordRow[];
}

export type AnalyticsType = "descriptive" | "diagnostic" | "predictive" | "prescriptive";

export interface Insight {
  analytics_type: AnalyticsType;
  type: string;
  severity: "positive" | "warning" | "info";
  title: string;
  detail: string;
  date?: string;
}

export interface Meta {
  min_date: string | null;
  max_date: string | null;
  record_count: number;
  entities: { entity_id: string; name: string; category: string | null }[];
  categories: string[];
  statuses: string[];
}

export interface FilterState {
  date_from: string;
  date_to: string;
  entity_id: string;
  category: string;
  status: string;
}

export const EMPTY_FILTERS: FilterState = {
  date_from: "",
  date_to: "",
  entity_id: "",
  category: "",
  status: "",
};

export interface UploadResult {
  mode: string;
  rows_loaded: number;
  rows_new: number;
  rows_updated: number;
  entities_created: number;
  date_min: string;
  date_max: string;
}

export interface SqlResult {
  columns: string[];
  rows: (string | number | boolean | null)[][];
  row_count: number;
  truncated: boolean;
  elapsed_ms: number;
  max_rows: number;
}

export interface SchemaObject {
  name: string;
  kind: "table" | "view";
  row_count: number;
  columns: { name: string; type: string }[];
}

export interface Exercise {
  id: string;
  title: string;
  level: number;
  concepts: string[];
  prompt: string;
  hint: string;
  ordered: boolean;
}

export interface CheckResult {
  correct: boolean;
  message: string;
  columns: string[];
  rows: SqlResult["rows"];
  row_count: number;
}

export interface ForecastPoint {
  date: string;
  forecast: number;
  lower: number;
  upper: number;
}

export type Forecast =
  | { available: false; reason: string }
  | {
      available: true;
      method: string;
      trend_per_day: number;
      trend_pct_per_day: number | null;
      residual_sd: number;
      backtest: { days: number; mape_pct: number } | null;
      points: ForecastPoint[];
    };

export interface ScatterData {
  total: number;
  sampled: boolean;
  points: { revenue: number; cost: number; units: number; entity_name: string; category: string }[];
}

export interface HeatmapData {
  days: string[];
  entities: string[];
  cells: { entity_name: string; day: string; avg_revenue: number; records: number }[];
}

export interface ExportDatasets {
  datasets: { id: string; table: string; description: string }[];
  formats: string[];
}

export interface ApacheFile { path: string; language: string; content: string }
export interface ApacheTool {
  id: string; name: string; role: string; summary: string;
  concepts: string[]; steps: string[]; files: ApacheFile[];
}

export interface NotebookInfo { file: string; title: string; summary: string; concepts: string[]; cells: number; needs_java: boolean }

export interface ScdType1Row { entity_id: string; name: string | null; category: string | null }
export interface ScdType2Row extends ScdType1Row { surrogate_key: number; valid_from: string; valid_to: string; is_current: boolean }
export interface ScdState { type1: ScdType1Row[]; type2: ScdType2Row[]; beginning: string; forever: string }
export interface ScdCompareRow { category: string; type1_revenue: number; type2_revenue: number; type1_records: number; type2_records: number; difference: number }
export interface ScdCompare { rows: ScdCompareRow[]; changes_made: number; total_type1: number; total_type2: number }

export type KpiStatus = "good" | "warn" | "bad" | "nodata";
export interface MetricInfo { id: string; label: string; unit: "usd" | "pct" | "count" | "min"; default_direction: "higher" | "lower"; description: string }
export interface Kpi {
  id: string; name: string; metric: string; label: string; unit: MetricInfo["unit"]; direction: "higher" | "lower";
  target: number; warn_pct: number; window_days: number; value: number | null; previous_value: number | null;
  gap: number | null; status: KpiStatus; window_start?: string; window_end?: string;
}

export interface QualityCheck { id: string; title: string; why: string; status: "ok" | "warn" | "bad"; count: number; sample: Record<string, string | number | null>[] }
export interface QualityReport {
  facts: number; entities: number; score_pct: number; passed: number; total_checks: number;
  nulls: { column: string; nulls: number; null_pct: number }[]; checks: QualityCheck[]; statuses: { status: string; rows: number }[];
}

export interface MlOptions {
  tasks: { id: string; label: string; kind: "regression" | "classification"; description: string }[];
  models: Record<"regression" | "classification", { id: string; label: string }[]>;
  features: { id: string; label: string; kind: "num" | "cat"; note: string }[];
  limits: { min_rows: number; max_rows: number };
}
export interface MlResult {
  task: string; kind: "regression" | "classification"; model: string; features: string[];
  split: { train_rows: number; test_rows: number; train_range: [string, string]; test_range: [string, string]; cutoff: string };
  metrics: Record<string, number | null>; baseline: Record<string, number | string | null>;
  primary_metric: { name: string; model: number | null; baseline: number | null };
  cv: { metric: string; scores: number[]; mean: number | null; std: number | null };
  confusion: { tn: number; fp: number; fn: number; tp: number } | null;
  importance: { feature: string; label: string; importance: number }[];
  sample: { actual: number; predicted: number }[];
  warnings: string[]; lessons: string[];
}
export type AiProviderId = "google" | "openai" | "anthropic";
export interface AiProviderStatus {
  id: AiProviderId; label: string; configured: boolean; sdk_installed: boolean; model: string;
  used_today: number; daily_limit: number; pip: string; key_env: string; role: string;
}
export interface AiStatus { providers: AiProviderStatus[]; ready: AiProviderId[]; max_steps: number }
export interface AiStep { tool: string; input: Record<string, unknown>; output: string; is_error: boolean }
export interface AiAttempt { provider: AiProviderId; ok: boolean; error: string; skipped?: boolean }
export interface AiAnswer {
  answer: string; model: string; provider: AiProviderId; stopped_early: boolean; steps: AiStep[];
  route: { kind: "simple" | "complex"; reason: string; forced: boolean } | null; attempts: AiAttempt[];
  usage: { input_tokens: number; output_tokens: number };
}

export interface TrackStep { kind: "page" | "notebook" | "file"; label: string; why: string; href?: string; path?: string }
export interface Track {
  id: string; name: string; role: string; summary: string;
  tools: { name: string; install: string }[]; path: TrackStep[]; projects: string[];
}
