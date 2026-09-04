import { useCallback, useEffect, useRef, useState } from "react";
import { BusinessImpact } from "./components/BusinessImpact";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { EvidenceLab } from "./components/EvidenceLab";
import { Footer } from "./components/Footer";
import { Hero } from "./components/Hero";
import { HowItWorks } from "./components/HowItWorks";
import { ModelPool } from "./components/ModelPool";
import { MoEvidence } from "./components/MoEvidence";
import { MoRouter } from "./components/MoRouter";
import { Nav } from "./components/Nav";
import { Operations } from "./components/Operations";
import { Results } from "./components/Results";
import { RouteArena } from "./components/RouteArena";
import { Skeleton } from "./components/ui";
import { useBootstrap, useMultiObjective, useSessionStats, useTheme } from "./hooks";
import { routeQuery } from "./lib/api";
import type { MultiObjective } from "./lib/api";
import type { RouteDecision } from "./lib/types";

const EMPTY_MO: MultiObjective = {
  available: false, objectives: null, pareto: null, privacy: null,
};

export function App() {
  const { data: boot, error: bootError, loading } = useBootstrap();
  const { theme, toggle } = useTheme();
  const { stats, refresh } = useSessionStats(4000);
  const { mo, loading: moLoading } = useMultiObjective();
  const moBundle = mo ?? EMPTY_MO;

  const [mode, setMode] = useState("balanced");
  const [threshold, setThreshold] = useState(0.95);
  const [query, setQuery] = useState("");
  const [queryClass, setQueryClass] = useState("");
  const [decision, setDecision] = useState<RouteDecision | null>(null);
  const [busy, setBusy] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);

  /** One routing round-trip. Threshold is passed explicitly so callers that
   *  just changed it (mode switch, auto-route) never race stale state. */
  const run = useCallback(
    async (q: string, cls: string, t: number) => {
      const text = q.trim();
      if (!text) return;
      setBusy(true);
      setRouteError(null);
      try {
        const d = await routeQuery({ query: text, query_class: cls || null, threshold: t });
        setDecision(d);
      } catch (e) {
        setDecision(null);
        setRouteError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
        refresh();
      }
    },
    [refresh]
  );

  // Open with a real, compelling decision already routed (a cheap win + savings).
  const autoRan = useRef(false);
  useEffect(() => {
    if (!boot || autoRan.current) return;
    autoRan.current = true;
    const balanced = boot.modes.modes.find((m) => m.key === "balanced");
    const t = balanced?.t ?? boot.modes.t_star ?? 0.95;
    if (balanced) setMode(balanced.key);
    setThreshold(t);
    const first = boot.scenarios.scenarios[0];
    if (first) {
      setQuery(first.query);
      setQueryClass(first.query_class);
      void run(first.query, first.query_class, t);
    }
  }, [boot, run]);

  const handleMode = useCallback(
    (key: string) => {
      setMode(key);
      const preset = boot?.modes.modes.find((m) => m.key === key);
      if (!preset) return;
      setThreshold(preset.t);
      if (query.trim()) void run(query, queryClass, preset.t);
    },
    [boot, query, queryClass, run]
  );

  const handleChallenge = useCallback(() => {
    const pool = boot?.scenarios.challenges ?? [];
    if (!pool.length) return;
    let pick = pool[Math.floor(Math.random() * pool.length)];
    for (let g = 0; pick.query === query && g < 12; g++) {
      pick = pool[Math.floor(Math.random() * pool.length)];
    }
    setQuery(pick.query);
    setQueryClass(pick.query_class);
    void run(pick.query, pick.query_class, threshold);
  }, [boot, query, run, threshold]);

  if (loading) return <Skeleton label="loading optiroute" />;

  if (bootError || !boot) {
    return (
      <>
        <div className="banner" role="alert">
          <span className="b-dot" aria-hidden="true" />
          <span>
            Failed to load dashboard data: {bootError ?? "unknown error"}. Is the routing
            server running on <code className="mono">127.0.0.1:8317</code>?
          </span>
        </div>
        <Skeleton label="waiting for the routing server" />
      </>
    );
  }

  const rows = boot.results.baselines_report ?? [];

  return (
    <>
      <Nav theme={theme} onToggleTheme={toggle} />

      <Hero boot={boot} />

      <main>
        <ErrorBoundary label="Route arena">
          <RouteArena
            boot={boot}
            stats={stats}
            mode={mode}
            onMode={handleMode}
            threshold={threshold}
            onThreshold={setThreshold}
            query={query}
            onQuery={setQuery}
            queryClass={queryClass}
            onQueryClass={setQueryClass}
            decision={decision}
            busy={busy}
            error={routeError}
            onRoute={() => void run(query, queryClass, threshold)}
            onRouteWith={(q, c) => void run(q, c, threshold)}
            onChallenge={handleChallenge}
          />
        </ErrorBoundary>
        <ErrorBoundary label="Multi-objective router">
          <MoRouter boot={boot} mo={moBundle} loading={moLoading} />
        </ErrorBoundary>
        <ErrorBoundary label="Pareto and privacy">
          <MoEvidence mo={moBundle} results={boot.results} />
        </ErrorBoundary>
        <ErrorBoundary label="Measured results">
          <Results rows={rows} />
        </ErrorBoundary>
        <ErrorBoundary label="Evidence lab">
          <EvidenceLab results={boot.results} />
        </ErrorBoundary>
        <ErrorBoundary label="Business impact">
          <BusinessImpact rows={rows} />
        </ErrorBoundary>
        <ErrorBoundary label="Operations">
          <Operations boot={boot} stats={stats} />
        </ErrorBoundary>
        <ErrorBoundary label="Model pool">
          <ModelPool models={boot.models} />
        </ErrorBoundary>
        <ErrorBoundary label="How it works">
          <HowItWorks />
        </ErrorBoundary>
      </main>

      <Footer />
    </>
  );
}
