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
  route: { kind: "simple" | "medium" | "complex"; reason: string; forced: boolean } | null; attempts: AiAttempt[];
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

export type SourceKind = "file" | "url" | "sql" | "html_table";
export interface DataSource {
  id: number; workspace: WorkspaceName; name: string; kind: SourceKind; config: Record<string, string | null>; target: string;
  interval_minutes: number; enabled: boolean; last_run_at: string | null; last_status: "ok" | "error" | null; last_message: string | null;
}
export interface SourceRun { at: string; ok: number; rows: number; message: string; seconds: number }
export interface SourcePreview { from: string; rows: number; columns: ColumnMeta[]; preview: Record<string, string | null>[] }
export interface InboxFiles { folders: string[]; files: { name: string; folder: string; path: string; size_bytes: number }[] }

export interface BackupItem { name: string; kind: string; size_bytes: number; created_at: string }
export interface AuditEntry { id: number; at: string; workspace: WorkspaceName; action: string; detail: string; ok: boolean }

// ---- Project & product management ----
export interface PmItem {
  id: number; kind: string; title: string; status: string; priority: number; owner: string | null; sprint_id: number | null; points: number | null;
  reach: number | null; impact: number | null; confidence: number | null; effort: number | null; value: number | null; time_crit: number | null; risk_red: number | null;
  moscow: string | null; start_date: string | null; duration_days: number | null; deps: number[]; planned_cost: number | null; actual_cost: number | null;
  started_at: string | null; done_at: string | null; notes: string | null;
}
export interface PmPct { avg: number; median: number; p85: number; n: number }
export interface PmSprint { id: number; name: string; start_date: string; end_date: string; goal: string | null; committed: number; completed: number; items: number; ended: boolean; completion_pct: number }
export interface PmRisk { id: number; title: string; probability: number; impact_usd: number; status: string; owner: string | null; mitigation: string | null; emv: number }
export interface PmKr { id: number; objective: string; kr: string; start_value: number; target_value: number; current_value: number; owner: string | null; progress_pct: number }
export interface PmFcast { sprints: number; date: string }
export interface PmOverview {
  as_of: string; items: PmItem[]; counts: Record<string, number>; empty: boolean;
  prioritization: { rows: { id: number; title: string; kind: string; status: string; moscow: string | null; points: number | null; rice: number | null; wsjf: number | null; rice_rank?: number }[]; moscow: Record<string, { items: number; points: number }>; moscow_unclassified: number; must_share_pct: number | null; unscored: number };
  flow: { done_count: number; cycle_days: PmPct; lead_days: PmPct; throughput_weekly: { week: string; done: number }[]; wip: number; littles_law: { throughput_per_day: number; avg_cycle_days: number; expected_wip: number; actual_wip: number }; cfd: { day: string; todo: number; doing: number; done: number }[] };
  sprint: { sprints: PmSprint[]; velocity: { history: number[]; avg_last3: number | null }; burndown: { sprint: string; committed: number; remaining: number; points: { day: string; ideal: number; actual: number | null }[]; status: string } | null; forecast: { remaining_points: number; avg_velocity: number; likely: PmFcast; fast: PmFcast; slow: PmFcast; note: string } | null };
  schedule: { available: boolean; duration_days?: number; finish?: string; rows: { id: number; title: string; status: string; duration: number; es: number; ef: number; ls: number; lf: number; float: number; critical: boolean; deps: number[]; start: string; finish: string }[]; critical: number[]; unknown_dependencies: number[]; reason?: string };
  earned_value: { available: boolean; as_of?: string; bac?: number; pv?: number; ev?: number; ac?: number; cpi?: number | null; spi?: number | null; cv?: number; sv?: number; eac?: number | null; etc?: number | null; vac?: number | null; tcpi?: number | null; unscheduled_items?: number; reading?: string; rule?: string; reason?: string };
  risks: { risks: PmRisk[]; open_count: number; exposure: number; matrix: number[][]; matrix_note: string; reserve_hint: string };
  okrs: { objectives: { objective: string; progress_pct: number; key_results: PmKr[] }[]; note: string };
  enums: { kinds: string[]; statuses: string[]; moscow: string[]; risk_status: string[] };
}
export interface PmProduct {
  available: boolean; last_day?: string; avg_dau?: number; mau?: number; stickiness_pct?: number | null;
  weekly_active?: { week: string; active: number; records: number }[]; funnel?: { stage: string; n: number; share_pct: number }[];
  cohorts?: { cohort: string; size: number; retention: (number | null)[] }[]; mapping?: string; stickiness_note?: string; reason?: string;
}

// ---- Systems analyst ----
export interface SaReq { id: number; code: string; title: string; kind: string; priority: string; status: string; source: string | null; acceptance: string | null; test_ref: string | null }
export interface SaFeas { rows: { key: string; label: string; question: string; score: number | null; weight: number; note: string }[]; weighted_score: number | null; verdict: string | null; weakest: string | null; scale?: string }
export interface SaOverview {
  requirements: SaReq[];
  traceability: { total: number; by_status: Record<string, number>; by_kind: Record<string, number>; test_coverage_pct: number | null; gaps: { code: string; title: string; problem: string }[]; note: string };
  enums: { kinds: string[]; priority: string[]; status: string[] };
  feasibility: SaFeas;
}
export interface SaDictionary {
  tables: { name: string; kind: string; columns: { name: string; type: string; nullable: boolean; key: string; description: string; null_pct: number | null; distinct: number | null }[]; rows: number; description: string }[];
  relationships: { from_table: string; from_column: string; to_table: string; to_column: string; meaning: string; orphans: number; valid: boolean }[];
  mermaid: string;
}
export interface SaProcess {
  available: boolean; reason?: string; records?: number; days?: number; duration?: { avg: number; p50: number; p85: number; p95: number; cv: number }; variability?: string;
  entities?: { entity: string; records: number; avg_min: number; p85_min: number; units: number; minutes: number; cost_per_unit: number | null; completion_pct: number | null; units_per_hour: number | null }[];
  statuses?: { status: string; n: number }[]; bottleneck?: { entity: string; p85_min: number; why: string };
  littles_law?: { arrivals_per_day: number; avg_minutes: number; avg_in_progress: number; reading: string };
  queue_inputs?: { arrivals_per_day: number; service_minutes: number };
}

// ---- Database admin and governance ----
export interface DbaHealth {
  workspace: string; engine: string; file: { name: string; size_bytes: number; wal_bytes: number; modified: string };
  blocks: { total: number; used: number; free: number; free_pct: number; block_size: number };
  tables: { name: string; rows: number; columns: number; has_pk: boolean; indexes: number }[]; views: number;
  constraints: { table: string; type: string; columns: string[] }[]; memory: { tag: string; bytes: number }[]; settings: { name: string; value: string }[];
  integrity: { name: string; ok: boolean; detail: string; fix?: string }[];
  backup: { count: number; latest: string | null; age_hours: number | null; auto: boolean; rpo: string };
  findings: { level: string; text: string; action: string }[]; growth: { at: string; size_bytes: number; rows_total: number }[]; access: string;
}
export interface DbaBench { threshold_ms: number; queries: { name: string; sql: string; median_ms: number; runs_ms: number[]; slow: boolean; scans: number; plan: string; note: string }[]; reading: string }
export interface GovAsset {
  name: string; kind: string; system: boolean; rows: number; columns: { name: string; type: string }[]; owner: string | null; steward: string | null; description: string | null;
  classification: string | null; retention_days: number | null; retention_column: string | null; completeness_pct: number | null; duplicate_rows: number;
  retention_eligible_rows: number | null; pii_columns: number; suggested_classification: string;
}
export interface GovCatalog { assets: GovAsset[]; classes: string[]; classes_help: Record<string, string> }
export interface GovPii { findings: { table: string; column: string; category: string; evidence: string; confidence: string; protected_from_ai: boolean }[]; unprotected: number; note: string }
export interface GovLineage { nodes: { id: string; kind: string }[]; edges: { from: string; to: string; kind: string }[]; consumers: { name: string; reads: string }[]; pipeline: string }
export interface GovControls { controls: { id: string; title: string; ok: boolean; detail: string; fix?: string }[]; in_place: number; total: number }
export interface GovAccess { since: string; by_action: { action: string; n: number; failed: number }[]; failed_total: number; data_leaving: { action: string; detail: string; at: string }[]; ai: { mode: string; blocked_columns: string[] }; note: string }

// ---- Full stack developer ----
export interface FsEndpoint { method: string; path: string; group: string; summary: string; params: { name: string; in: string; required: boolean; type: string }[]; json_body: boolean; sample_body: Record<string, null> | null; multipart: boolean }
export interface FsApiMap { title: string; version: string; total: number; by_method: Record<string, number>; groups: { group: string; endpoints: number }[]; endpoints: FsEndpoint[] }
export interface FsResponse { method: string; path: string; status: number; ms: number; content_type: string; truncated: boolean; body: string; reading: string }
export interface FsScaffold { table: string; primary_key: string | null; columns: number; route: string; files: { name: string; language: string; content: string }[]; next_steps: string[]; caveat: string }
export interface FsCodebase { languages: { language: string; files: number; lines: number }[]; files: number; tests: number; route_functions: number; test_to_python_ratio: number | null; largest: { file: string; lines: number }[]; reading: string }
export interface FsStack { python: string; platform: string; packages: Record<string, string | null>; tools_on_path: Record<string, boolean>; facts: { area: string; value: string; note: string }[]; reading: string }

// ---- Company engagement ----
export interface CoDeliverable { id: string; discipline: string; title: string; why: string; href: string; auto: boolean; detected: boolean; manual: boolean; done: boolean; detail: string; note: string; due: string; overdue: boolean; due_soon: boolean }
export interface CoOverview {
  workspace: WorkspaceName; brief: { company: string; goal: string; notes: string };
  phases: { id: string; name: string; about: string; done: number; total: number; deliverables: CoDeliverable[] }[];
  disciplines: { id: string; name: string; does: string; total: number; done: number; learning_done: number; learning_total: number; href: string }[];
  done: number; total: number; pct: number; next: CoDeliverable | null; note: string; overdue: number; due_soon: number;
}

// ---- Manuals and discipline agents ----
export interface ManualStep { id: string; title: string; what: string; how: string[]; tool: { label: string; href: string | null; tab: string | null } | null; done_when: string; mistakes: string[]; ask: string }
export interface Manual { track: string; title: string; intro: string; outcome: string; steps: ManualStep[]; done: string[] }
export interface AgentInfo {
  track: string; name: string; focus: string; can_propose: string[]; can: string[]; suggestions: string[];
  status: { ready: string[]; policy: { mode: string; allowed: boolean; workspace: string; blocked_columns: string[] } };
}
export interface AgentProposal { type: string; data: Record<string, unknown>; reason: string }
export interface AgentAction { tab?: string; href?: string; label: string }
export interface AgentMsg { role: "user" | "agent"; content: string; proposals?: AgentProposal[]; actions?: AgentAction[]; meta?: string; error?: boolean; trace?: AgentTrace }

// ---- Update 12: usage, evals, company extras, alerts, drill, time, compare, quizzes, search ----
export interface AiUsage {
  days: number; total_questions: number; total_tokens: number; total_cost_usd: number | null; cost_note: string; caps_note: string;
  today: { provider: AiProviderId; label: string; configured: boolean; used: number; limit: number; pct: number; model: string }[];
  daily: ({ day: string; total: number; tokens: number } & Record<AiProviderId, number>)[];
  matrix: Record<"simple" | "medium" | "complex", Record<AiProviderId, number>>;
  by_track: Record<string, number>;
  tokens: Record<AiProviderId, { input: number; output: number; cost_usd: number | null }>;
  recent: { created_at: string; question: string; provider: string; model: string; tier: string; track: string | null; tin: number; tout: number }[];
}
export interface EvalCheck { name: string; ok: boolean; detail: string }
export interface EvalRun {
  at: string; track: string; mode: "route" | "live"; models: string[]; passed: number; total: number; pct: number;
  results: { id: string; ask: string; expected_tier: string; ok: boolean; reply: string; provider: string; model: string; seconds: number | null; checks: EvalCheck[] }[];
}
export interface EvalOverview { tracks: { track: string; name: string; cases: { id: string; ask: string; tier: string }[] }[]; runs: EvalRun[]; max_live_cases: number; note: string }
export interface CoSnapshot { id?: number; at: string; kind: string; done: number; total: number; pct: number; brief: string; ai: boolean; provider?: string; model?: string }
export interface AlertItem { id: string; level: "red" | "warn"; title: string; detail: string; href: string }
export interface AlertStatus {
  config: { enabled: boolean; email: boolean; stale_days: number; backup_days: number; cooldown_hours: number }; email_ready: boolean;
  options: { cooldown_hours: number[] }; alerts: AlertItem[]; red: number; emailed: string[]; email_problem: string | null; checked_at: string;
}
export interface DrillEntry {
  at: string; backup: string; ok: boolean; seconds: number; steps: { name: string; ok: boolean; detail: string }[]; backup_age_hours: number;
  records_since_backup: number | null; reading: string; recovery_point: string;
}
export interface PmTime {
  rate: number; total_hours: number; unassigned_hours: number; cost: number | null; feeds_earned_value: boolean; note: string;
  entries: { id: number; item_id: number | null; item_title: string; day: string; hours: number; note: string }[];
  by_item: { item_id: number; title: string; status: string; hours: number; cost: number | null; planned_cost: number | null; over_plan: boolean }[];
  weeks: { week: string; hours: number }[];
}
export interface CompareData {
  active: WorkspaceName; exists: Record<WorkspaceName, boolean>; real_has_data: boolean; note: string; kpi_note: string; errors: Record<string, string>;
  metrics: { key: string; label: string; unit: string; practice: number | string | null; real: number | string | null; delta: { abs: number; pct: number | null } | null }[];
  tables: { table: string; practice: number | null; real: number | null }[];
  schema_differences: { table: string; only_practice: string[]; only_real: string[] }[];
  top_entities: Record<WorkspaceName, { name: string; revenue: number }[]>;
  kpis: { name: string; label: string; target: number; direction: string; practice: { value: number | null; status: string; unit: string } | null; real: { value: number | null; status: string; unit: string } | null }[];
}
export interface QuizData { track: string; pass_pct: number; result: QuizResult | null; questions: { id: number; step: string; step_title: string; q: string; options: string[] }[] }
export interface QuizResult { best_pct: number; last_pct: number; attempts: number; passed: boolean; last_at: string; missed_steps: string[] }
export interface QuizGraded { score: number; total: number; pct: number; passed_now: boolean; result: QuizResult; graded: { id: number; ok: boolean; picked: number; correct: number; why: string; step: string }[]; review: string[] }
export interface SearchHit { kind: string; title: string; sub: string; href: string }
export interface AgentTrace { route: { kind: string; reason: string; forced: boolean } | null; model: string; provider: string; tools: { tool: string; error: boolean; what: string; chars: number }[]; tokens_in: number; tokens_out: number }
