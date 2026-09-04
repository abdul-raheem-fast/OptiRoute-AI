/* API contract types — mirrors webapp/server.py + webapp/router_core.py. */

/** GET /api/models */
export interface ModelRow {
  model: string;
  provider: string;
  price_in: number | null;
  price_out: number | null;
  avg_cost_per_query: number;
  avg_latency_s: number;
  class_accuracy: Record<string, number>;
}
export interface ModelsPayload {
  models: ModelRow[];
  classes: string[];
  t_star: number;
}

/** One row of routing/results/baselines_report.csv (via GET /api/results). */
export interface PolicyRow {
  policy: string;
  accuracy_pct: number;
  quality_vs_strongest_pct: number;
  avg_cost_per_query: number;
  avg_latency_s: number;
  cost_reduction_vs_strongest_pct: number;
  meets_quality_floor: boolean;
  oracle_gap_pts: number;
}

export interface SplitsManifest {
  seed: number;
  fracs: Record<string, number>;
  tier_rules: Record<string, [number, number]>;
  strata: Record<string, Record<string, number>>;
  queries: number;
  split_counts: { train: number; val: number; test: number };
  aligned7_duplicate_ids: number;
  duplicate_ids_in_val_or_test: string[] | number[];
  note?: string;
}

/** GET /api/results */
export interface ResultsPayload {
  baselines_report: PolicyRow[];
  learned_router_report?: Record<string, unknown>[];
  oracle_report?: Record<string, unknown>[];
  threshold_curves?: Record<string, unknown>[];
  mo_eval_report?: MoEvalRow[];
  splits_manifest?: SplitsManifest;
}

/** One row of routing/results/mo_eval_report.csv (sealed-test MO evaluation).
 *  Also carries mix_<model> percentage columns (left open via the index sig). */
export interface MoEvalRow {
  policy: string;
  accuracy_pct: number;
  quality_vs_gpt5_pct: number;
  avg_cost_per_query: number;
  cost_reduction_vs_gpt5_pct: number;
  avg_latency_s: number;
  p50_latency_s: number;
  p95_latency_s: number;
  p99_latency_s: number;
  latency_delta_vs_gpt5_s: number;
  privacy_filtered_pct: number;
  [key: string]: number | string;
}

/** GET /api/modes */
export interface ModePreset {
  key: "economy" | "balanced" | "quality" | string;
  label: string;
  description: string;
  t: number;
  val_accuracy_pct: number | null;
  val_avg_cost_per_query: number | null;
  meets_floor: boolean;
  measured_on: string;
}
export interface ModesPayload {
  modes: ModePreset[];
  t_star: number;
}

/** GET /api/scenarios */
export interface Scenario {
  label: string;
  dot: "easy" | "medium" | "hard";
  query: string;
  query_class: string;
  expected_model: string;
  expected_saving_pct: number;
  expected_route: "cheap" | "escalate";
}
export interface Challenge {
  query: string;
  query_class: string;
  expected_route: "cheap" | "escalate";
}
export interface ScenariosPayload {
  scenarios: Scenario[];
  challenges: Challenge[];
  source: string;
}

/** POST /api/route response (webapp/router_core.py :: RouterCore.route). */
export interface CascadeStep {
  model: string;
  p_correct: number;
  passes: boolean;
}
export interface WhyNotStrongest {
  delta_accuracy_pts: number;
  delta_cost_per_query: number;
  verdict: string;
}
export interface RouteDecision {
  query_class: string;
  threshold: number;
  chosen_model: string;
  chosen_index: number;
  is_fallback: boolean;
  tier: string | null;
  tier_probs: Record<string, number> | null;
  reasons: string[];
  why_not_strongest: WhyNotStrongest;
  p_correct: Record<string, number>;
  cascade_trace: CascadeStep[];
  est_cost_per_query: number;
  est_latency_s: number;
  strongest_cost_per_query: number;
  est_saving_pct: number;
  class_prior_acc: Record<string, number>;
}

/** GET /api/stats — demo-session telemetry, not production traffic. */
export interface RouteLogEntry {
  model: string;
  tier: string | null;
  saved: number;
  fallback: boolean;
}
export interface StatsPayload {
  session_queries: number;
  distribution: Record<string, number>;
  escalations: number;
  efficient_routes: number;
  escalation_rate_pct: number;
  est_savings_total: number;
  tier_distribution: Record<string, number>;
  route_log: RouteLogEntry[];
}

/** Everything the dashboard needs, fetched once at boot. */
export interface Bootstrap {
  models: ModelsPayload;
  results: ResultsPayload;
  modes: ModesPayload;
  scenarios: ScenariosPayload;
}

/* ==========================================================================
   Multi-objective router contract — mirrors routing/objectives.py,
   routing/models/mo_objectives.json, webapp/mo_router.py and the new
   /api/objectives, /api/pareto, /api/privacy, /api/sensitivity endpoints.
   ========================================================================== */

export type MoMode = "economy" | "balanced" | "speed" | "quality" | "private";

/** One measured val-split verification block (a mode, or the legacy router). */
export interface MoValMetrics {
  accuracy_pct: number;
  avg_cost_per_query: number;
  avg_latency_s: number;
  p50_latency_s: number;
  p95_latency_s: number;
  p99_latency_s: number;
}

/** A configurable routing objective (routing/objectives.py -> mo_objectives.json). */
export interface MoModeSpec {
  label: string;
  description: string;
  lambda_cost: number;
  lambda_latency: number;
  quality_floor_rule: string | null;
  policy_quality_floor_pct: number | null;
  latency_budget_rule: string | null;
  latency_budget_ms: number | null;
  privacy_restricted: boolean;
  eligible_models: string[];
  val: MoValMetrics;
  val_meets_floor: boolean | null;
  val_model_mix: Record<string, number>;
  notes: string;
}

export interface MoTrainStat {
  accuracy: number;
  cost: number;
  latency_s: number;
  latency_ms: number;
}

/** Platt calibration per head + honest train/val diagnostics. */
export interface MoCalibration {
  a: number;
  b: number;
  train: { mean_gap_pts: number; ece: number };
  val: { mean_gap_pts: number; ece: number };
}

export interface MoNormalization {
  cost_min: number;
  cost_max: number;
  latency_min: number;
  latency_max: number;
}

export interface MoFrontiers {
  global: string[];
  quality_floor: string[];
  privacy_approved: string[];
}

/** GET /api/objectives */
export interface ObjectivesPayload {
  available: boolean;
  default_router: string;
  mode_order: MoMode[];
  modes: Record<MoMode, MoModeSpec>;
  normalization: MoNormalization;
  measured_train_stats: Record<string, MoTrainStat>;
  calibration: Record<string, MoCalibration>;
  legacy_val: MoValMetrics & { val_model_mix: Record<string, number>; t_star: number };
  meta: Record<string, unknown>;
}

/** GET /api/pareto */
export interface ParetoPoint {
  model: string;
  quality: number;
  cost: number;
  latency_s: number;
  dominated_by: string[];
  on_global_frontier: boolean;
}
export interface ParetoPayload {
  dimensions: Record<string, string>;
  points: ParetoPoint[];
  frontiers: MoFrontiers;
  note: string;
}

/** GET /api/privacy */
export interface ModelPrivacy {
  privacy_level: string;
  external_api: boolean;
  locally_hosted: boolean;
  data_retention: string;
  approved_for_sensitive: boolean;
  source?: string;
}
export interface PrivacyPayload {
  deployment: {
    allow_external_models: boolean;
    allow_sensitive_queries: boolean;
    approved_for_sensitive: string[];
    note?: string;
  };
  models: Record<string, ModelPrivacy>;
  sensitivity_rules: { n_patterns: number; keywords: string[] };
  provenance: Record<string, string> | string;
  note: string;
}

/** POST /api/sensitivity — the deterministic LOCAL classifier result. */
export interface SensitivityResult {
  sensitivity: "normal" | "sensitive";
  reason: string;
}

/** Per-model breakdown row inside a multi-objective decision. */
export interface MoModelScore {
  model: string;
  routing_score: number;
  raw_score: number;
  utility: number;
  eligible: boolean;
  admissible: boolean;
  on_global_frontier: boolean;
  measured_accuracy_pct: number;
  measured_cost_per_query: number;
  measured_latency_ms: number;
}

export interface MoLatency {
  router_overhead_ms: number;
  model_inference_ms: number;
  end_to_end_ms: number;
  note?: string;
}

export interface MoConstraints {
  quality_floor: number | null;
  latency_budget_ms: number | null;
  latency_budget_met: boolean | null;
  privacy_restricted: boolean;
  lambda_cost: number;
  lambda_latency: number;
}

export interface MoWhyNotStrongest {
  strongest_model: string;
  delta_quality_pts: number;
  delta_cost_per_query: number;
  verdict: string;
}

export interface MoParetoInfo {
  on_frontier: string[];
  global_frontier: string[];
  is_strongest_eligible: boolean;
}

/** POST /api/route response when the multi-objective router answers. */
export interface MoRouteDecision {
  router: "multi_objective";
  selected_model: string | null;
  chosen_model: string | null;
  chosen_index?: number;
  mode: MoMode;
  mode_label: string;
  query_class: string;
  is_fallback: boolean;
  routing_score: number | null;
  predicted_quality?: number | null;
  estimated_cost_per_query: number;
  strongest_cost_per_query: number;
  estimated_latency_ms?: number;
  estimated_latency_s?: number;
  latency: MoLatency;
  privacy_status: "approved" | "blocked";
  sensitivity: SensitivityResult;
  sensitive: boolean;
  privacy_note?: string;
  constraints: MoConstraints;
  reason: string;
  reason_code: string;
  pareto: MoParetoInfo;
  why_not_strongest?: MoWhyNotStrongest;
  est_saving_pct?: number;
  eligible_models: string[];
  model_scores?: MoModelScore[];
  calibrated_quality: Record<string, number>;
}
