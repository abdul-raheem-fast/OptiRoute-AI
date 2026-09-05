import { StatTile } from "./ui";
import { fmtInt } from "../lib/format";
import type { Bootstrap } from "../lib/types";

/** Cost spread across the pool: priciest model vs cheapest priced model. */
function costSpread(boot: Bootstrap): number | null {
  const costs = boot.models.models
    .map((m) => m.avg_cost_per_query)
    .filter((c) => Number.isFinite(c) && c > 0);
  if (costs.length < 2) return null;
  return Math.max(...costs) / Math.min(...costs);
}

export function Hero({ boot }: { boot: Bootstrap }) {
  const rows = boot.results.baselines_report ?? [];
  const learned = rows.find((r) => r.policy.startsWith("learned"));
  const strongest = rows.find((r) => r.policy === "always-strongest");
  const oracle = rows.find((r) => r.policy === "oracle");
  const spread = costSpread(boot);
  const testN = boot.results.splits_manifest?.split_counts?.test ?? 282;

  return (
    <section className="hero" id="top">
      <div className="container">
        <span className="hero-badge">
          <span className="live" aria-hidden="true" />
          router online &middot; {boot.models.models.length} models &middot;{" "}
          {fmtInt(1887)} aligned benchmark queries
        </span>

        <h1>
          Route every query to the <span className="grad-text">cheapest model</span> that
          will get it right.
        </h1>

        <p className="hero-lead">
          Eight production LLMs, five capability classes. A learned cascade decides{" "}
          <em>before dispatch</em> which model each query actually needs. Cost is the
          objective; quality is the constraint.
        </p>

        <div className="hero-actions">
          <a className="btn btn--primary" href="#router">
            Try the live router
          </a>
          <a className="btn btn--ghost" href="#results">
            See the measured results
          </a>
        </div>

        <div className="stat-grid">
          <StatTile
            accent
            value={learned ? learned.cost_reduction_vs_strongest_pct.toFixed(1) : "—"}
            unit="%"
            label="Cost cut vs always-GPT-5"
          />
          <StatTile
            value={learned ? learned.quality_vs_strongest_pct.toFixed(1) : "—"}
            unit="%"
            label="Of flagship quality retained"
          />
          <StatTile
            value={spread ? fmtInt(spread) : "—"}
            unit={spread ? "×" : undefined}
            label="Cost spread across the model pool"
          />
          <StatTile
            value={oracle ? oracle.cost_reduction_vs_strongest_pct.toFixed(1) : "—"}
            unit="%"
            label="Oracle ceiling cost reduction"
          />
        </div>

        <p className="hero-note">
          Measured on the held-out test split ({fmtInt(testN)} queries). Quality floor = 90% of
          always-strongest accuracy{strongest ? ` (${strongest.accuracy_pct.toFixed(2)}%)` : ""}.
        </p>
      </div>
    </section>
  );
}
