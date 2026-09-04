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
  splits_manifest?: SplitsManifest;
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
