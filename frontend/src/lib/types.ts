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
export interface AiPolicy { workspace: WorkspaceName; mode: AiMode; blocked_columns: string[]; allowed: boolean }
export interface AiStatus { providers: AiProviderStatus[]; ready: AiProviderId[]; max_steps: number; policy?: AiPolicy }
export interface AiStep { tool: string; input: Record<string, unknown>; output: string; is_error: boolean }
export interface AiAttempt { provider: AiProviderId; ok: boolean; error: string; skipped?: boolean }
export interface AiChart { kind: "line" | "bar"; title: string; x_label: string; y_label: string; points: { x: string; y: number }[]; truncated: boolean; sql: string }
export interface AiAnswer {
  chart: AiChart | null;
  answer: string; model: string; provider: AiProviderId; stopped_early: boolean; steps: AiStep[];
  route: { kind: "simple" | "complex"; reason: string; forced: boolean } | null; attempts: AiAttempt[];
  usage: { input_tokens: number; output_tokens: number };
}

export interface TrackStep { id: string; kind: "page" | "notebook" | "file"; label: string; why: string; href?: string; path?: string }
export interface Track {
  id: string; name: string; role: string; summary: string;
  tools: { name: string; install: string }[]; path: TrackStep[]; projects: string[];
}

export interface TrackProgress {
  id: string; name: string; done: number; total: number; pct: number; last_activity: string | null;
  next: { id: string; kind: "page" | "notebook" | "file"; label: string; href?: string; path?: string; why: string } | null;
}
export interface Progress {
  done: string[]; tracks: TrackProgress[]; overall_pct: number;
  continue: { track: string; track_name: string; step: NonNullable<TrackProgress["next"]> } | null;
}

export interface GlossaryTerm {
  id: string; term: string; kind: "Metric" | "KPI" | "Concept" | "Method"; definition: string; formula: string; sql: string; pitfall: string; additive?: boolean;
}

export interface PipelineLayer { layer: string; label: string; rows: number; files: number }
export interface PipelineRun { at: string; source: string; reset: boolean; seconds: number; bronze_rows: number; silver_rows: number; quarantined: number; gold_rows: number; watermark_before: string | null; watermark_after: string | null }
export interface PipelineStatus {
  exists: boolean; message?: string; watermark?: string | null; loads?: number; layers?: PipelineLayer[];
  quarantine_reasons?: { reason: string; rows: number }[]; checks?: { name: string; ok: boolean; detail: string }[]; history: PipelineRun[];
}

type Unavailable = { available: false; reason: string };
export interface AnalystDash {
  kpis: { records: number; revenue: number; cost: number; profit: number; margin_pct: number; vs_budget_pct: number | null; completion_pct: number };
  over_budget: { entity: string; category: string | null; overspend_usd: number; vs_budget_pct: number; records: number }[];
  weekly_margin: { week: string; margin_pct: number; revenue: number }[];
  status_mix: { status: string; n: number }[];
  quality: { score_pct: number; passed: number; total: number; failing: string[] };
  ideas: string[];
}
export interface ScientistDash {
  weekend_test: Unavailable | { available: true; weekend_days: number; weekday_days: number; weekend_mean: number; weekday_mean: number; diff: number; ci_low: number; ci_high: number; t: number; p_value: number; verdict: string };
  segments: Unavailable | { available: true; keys: string[]; segments: { segment: number; entities: string[]; means: Record<string, number> }[] };
  correlations: Unavailable | { available: true; names: string[]; matrix: (number | null)[][] };
  ideas: string[];
}
export interface MlRun { created_at: string; task: string; model: string; features: string[]; metric: string; model_score: number | null; baseline_score: number | null; test_rows: number }
export interface MlDash { runs: MlRun[]; total_runs: number; best: (MlRun & { lift: number | null })[]; ideas: string[] }
export interface EngineeringDash { pipeline: PipelineStatus; ideas: string[] }
export interface AiDash {
  providers: AiProviderStatus[]; ready: AiProviderId[]; ideas: string[];
  log: { totals: { questions: number; tin: number; tout: number; charts: number }; by_provider: { provider: string; questions: number }[];
         recent: { created_at: string; question: string; provider: string; kind: string; ok: boolean }[] };
}

export interface BreakdownRow { name: string; value: number; records: number; revenue: number; cost: number; units: number }
export interface Breakdown {
  by: string; by_label: string; measure: string; measure_label: string; format: "money" | "number";
  total: number; grouped_into_other: boolean; rows: BreakdownRow[];
}
export interface BoxStat {
  name: string; n: number; whisker_low: number; q1: number; median: number; q3: number; whisker_high: number;
  mean: number; outliers: number[]; outlier_count: number;
}
export interface Distribution {
  measure: string; measure_label: string; format: "money" | "number"; count: number; bins?: number;
  histogram: { from: number; to: number; count: number }[]; boxes: BoxStat[];
}
export interface BubbleData { rows: { name: string; category: string; cost: number; revenue: number; units: number }[] }

export interface DatasetCheck { ok: boolean; need: string; have: string }
export interface DatasetCareer { id: string; name: string; uses: string; ready: boolean; checks: DatasetCheck[] }
export interface DatasetInfo {
  rows: number; entities: number; days: number; date_min: string | null; date_max: string | null;
  weekend_days: number; weekday_days: number; careers: DatasetCareer[];
}

// ---- Real-use features: workspaces, imported tables, sources, backups, activity ----
export type WorkspaceName = "practice" | "real";
export type AiMode = "off" | "aggregate" | "full";
export interface WorkspaceSettings { ai_mode: AiMode; blocked_columns: string[]; backup_keep: number; auto_backup: boolean }
export interface WorkspaceInfo {
  name: WorkspaceName; label: string; active: boolean; exists: boolean; size_bytes: number; settings: WorkspaceSettings;
  records?: number; tables?: number;
}
export interface WorkspaceList { active: WorkspaceName; workspaces: WorkspaceInfo[] }

export interface ColumnMeta { name: string; type: string }
export interface UserTable { table_name: string; label: string; source: string; rows_count: number; columns: ColumnMeta[]; created_at: string; updated_at: string }
export interface PreviewColumn { name: string; original: string; type: string; samples: string[] }
export interface OpsField { field: string; required: boolean; hint: string }
export interface FilePreview {
  filename: string; rows_total: number; header: string[]; columns: PreviewColumn[]; preview: Record<string, string | null>[];
  suggested_name: string; delimiter?: string; sheets?: string[]; sheet?: string;
  operations: { fields: OpsField[]; suggested: Record<string, string> };
}
export interface ImportResult { table: string; rows: number; added: number; mode: string; columns: ColumnMeta[] }
export interface ProfileColumn {
  name: string; type: string; kind: "number" | "date" | "text" | "bool"; nulls: number; distinct_count: number;
  min?: number | string | null; max?: number | string | null; mean?: number | null; median?: number | null; top?: { value: string; n: number }[];
}
export interface TableProfile { table: string; rows: number; columns: ProfileColumn[] }
export interface TableAggregate { x: string; measure: string; series: string[]; data: Record<string, string | number | null>[] }
export interface TableHistogram { column: string; n: number; bins: { start: number; end: number; label: string; count: number }[] }
export interface TableBox { column: string; by: string | null; boxes: { name: string; mn: number; q1: number; med: number; q3: number; mx: number; mean: number; n: number }[] }
export interface TableScatter { x: string; y: string; n: number; shown: number; correlation: number | null; points: { x: number; y: number }[] }

export type SourceKind = "file" | "url" | "sql";
export interface DataSource {
  id: number; workspace: WorkspaceName; name: string; kind: SourceKind; config: Record<string, string | null>; target: string;
  interval_minutes: number; enabled: boolean; last_run_at: string | null; last_status: "ok" | "error" | null; last_message: string | null;
}
export interface SourceRun { at: string; ok: number; rows: number; message: string; seconds: number }
export interface SourcePreview { from: string; rows: number; columns: ColumnMeta[]; preview: Record<string, string | null>[] }
export interface InboxFiles { folders: string[]; files: { name: string; folder: string; path: string; size_bytes: number }[] }

export interface BackupItem { name: string; kind: string; size_bytes: number; created_at: string }
export interface AuditEntry { id: number; at: string; workspace: WorkspaceName; action: string; detail: string; ok: boolean }
