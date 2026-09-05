import { BusinessImpact } from "./components/BusinessImpact";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { EvidenceLab } from "./components/EvidenceLab";
import { Footer } from "./components/Footer";
import { Hero } from "./components/Hero";
import { HowItWorks } from "./components/HowItWorks";
import { ModelPool } from "./components/ModelPool";
import { MoEvidence } from "./components/MoEvidence";
import { Nav } from "./components/Nav";
import { Operations } from "./components/Operations";
import { RouterSection } from "./components/RouterSection";
import { Collapsible, Skeleton } from "./components/ui";
import { useBootstrap, useMultiObjective, useSessionStats, useTheme } from "./hooks";
import type { MultiObjective } from "./lib/api";

const EMPTY_MO: MultiObjective = {
  available: false, objectives: null, pareto: null, privacy: null,
};

export function App() {
  const { data: boot, error: bootError, loading } = useBootstrap();
  const { theme, toggle } = useTheme();
  const { stats } = useSessionStats(4000);
  const { mo, loading: moLoading } = useMultiObjective();
  const moBundle = mo ?? EMPTY_MO;

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
        {/* 01 — the one live router: multi-objective (default) + legacy research baseline */}
        <ErrorBoundary label="Live router">
          <RouterSection boot={boot} mo={moBundle} loading={moLoading} />
        </ErrorBoundary>

        {/* 02 — measured results: Pareto + sealed-test tradeoff, baselines & privacy folded */}
        <ErrorBoundary label="Measured results">
          <MoEvidence mo={moBundle} results={boot.results} />
        </ErrorBoundary>

        {/* 03 — the model pool */}
        <ErrorBoundary label="Model pool">
          <ModelPool models={boot.models} />
        </ErrorBoundary>

        {/* 04 — how it works */}
        <ErrorBoundary label="How it works">
          <HowItWorks />
        </ErrorBoundary>

        {/* Deep dive — provenance, savings and telemetry, folded away by default so the
            demo view stays focused. Native <details>, so it works without JavaScript. */}
        <section className="section" id="deepdive">
          <div className="container">
            <Collapsible title="Deep dive" hint="provenance · savings projection · live telemetry">
              <ErrorBoundary label="Evidence lab">
                <EvidenceLab results={boot.results} />
              </ErrorBoundary>
              <ErrorBoundary label="Business impact">
                <BusinessImpact rows={rows} />
              </ErrorBoundary>
              <ErrorBoundary label="Operations">
                <Operations boot={boot} stats={stats} />
              </ErrorBoundary>
            </Collapsible>
          </div>
        </section>
      </main>

      <Footer />
    </>
  );
}
