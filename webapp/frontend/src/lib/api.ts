import type {
  Bootstrap,
  ModesPayload,
  ModelsPayload,
  RouteDecision,
  ResultsPayload,
  ScenariosPayload,
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
