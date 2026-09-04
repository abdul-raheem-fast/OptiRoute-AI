import type {
  Bootstrap,
  ModesPayload,
  ModelsPayload,
  MoMode,
  MoRouteDecision,
  ObjectivesPayload,
  ParetoPayload,
  PrivacyPayload,
  RouteDecision,
  ResultsPayload,
  ScenariosPayload,
  SensitivityResult,
  StatsPayload,
} from "./types";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** Load every payload the dashboard needs, in parallel. */
export async function loadBootstrap(): Promise<Bootstrap> {
  const [models, results, modes, scenarios] = await Promise.all([
    getJSON<ModelsPayload>("/api/models"),
    getJSON<ResultsPayload>("/api/results"),
    getJSON<ModesPayload>("/api/modes"),
    getJSON<ScenariosPayload>("/api/scenarios"),
  ]);
  return { models, results, modes, scenarios };
}

export interface RouteArgs {
  query: string;
  query_class?: string | null;
  threshold?: number | null;
  mode?: string | null;
}

/** POST /api/route — one live routing decision (no external model calls). */
export async function routeQuery(args: RouteArgs): Promise<RouteDecision> {
  const res = await fetch("/api/route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: args.query,
      query_class: args.query_class ?? null,
      threshold: args.threshold ?? null,
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as RouteDecision;
}

export function loadStats(): Promise<StatsPayload> {
  return getJSON<StatsPayload>("/api/stats");
}

/* ---------------------------------------------------------------------------
   Multi-objective router (experimental/advanced path).
   --------------------------------------------------------------------------- */

export interface MultiObjective {
  /** True only when the fitted artifact is present (objectives + pareto load). */
  available: boolean;
  objectives: ObjectivesPayload | null;
  pareto: ParetoPayload | null;
  privacy: PrivacyPayload | null;
}

/**
 * Load the multi-objective payloads. Degrades gracefully on purpose:
 * /api/objectives and /api/pareto return 503 when
 * routing/models/mo_objectives.json has not been built, and /api/privacy works
 * regardless. A missing artifact must never break the legacy dashboard, so each
 * call is isolated and failures resolve to null.
 */
export async function loadMultiObjective(): Promise<MultiObjective> {
  const safe = async <T>(p: Promise<T>): Promise<T | null> => {
    try {
      return await p;
    } catch {
      return null;
    }
  };
  const [objectives, pareto, privacy] = await Promise.all([
    safe(getJSON<ObjectivesPayload>("/api/objectives")),
    safe(getJSON<ParetoPayload>("/api/pareto")),
    safe(getJSON<PrivacyPayload>("/api/privacy")),
  ]);
  return { available: objectives != null, objectives, pareto, privacy };
}

export interface MoRouteArgs {
  query: string;
  query_class?: string | null;
  mode?: MoMode | null;
  quality_floor?: number | null;
  latency_budget_ms?: number | null;
  sensitive?: boolean | null;
}

/** POST /api/route through the multi-objective router (explicit opt-in). The
 *  decision itself is pure local arithmetic - no external model call. */
export async function routeMo(args: MoRouteArgs): Promise<MoRouteDecision> {
  const body: Record<string, unknown> = {
    query: args.query,
    router: "multi_objective",
    query_class: args.query_class ?? null,
    mode: args.mode ?? null,
  };
  if (args.quality_floor != null) body.quality_floor = args.quality_floor;
  if (args.latency_budget_ms != null) body.latency_budget_ms = args.latency_budget_ms;
  if (args.sensitive != null) body.sensitive = args.sensitive;
  const res = await fetch("/api/route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as MoRouteDecision;
}

/** POST /api/sensitivity — the deterministic LOCAL sensitivity classifier. */
export async function classifySensitivity(query: string): Promise<SensitivityResult> {
  const res = await fetch("/api/sensitivity", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as SensitivityResult;
}
