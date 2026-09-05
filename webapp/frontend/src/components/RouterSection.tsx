import { useState } from "react";
import { Section, Segmented } from "./ui";
import { MoRouter } from "./MoRouter";
import { RouteArena } from "./RouteArena";
import type { Bootstrap } from "../lib/types";
import type { MultiObjective } from "../lib/api";

/** Which router body is showing. Multi-objective is the default experience; the
 *  legacy cascade is kept as a validated research baseline for comparison. */
type Strategy = "mo" | "legacy";

interface Props {
  boot: Bootstrap;
  mo: MultiObjective;
  loading: boolean;
}

const LEAD: Record<Strategy, string> = {
  mo: "The default experience — balance quality, cost, latency and privacy, behind hard privacy and latency constraints.",
  legacy: "The validated cost-optimized cascade, kept as a research baseline for comparison.",
};

/**
 * The ONE router section (id="router", index 01). Owns the shared heading and a small
 * strategy switch, then renders exactly one body at a time:
 *   • Multi-Objective (default)  -> <MoRouter/>
 *   • Research Baseline (legacy) -> <RouteArena/>
 * Neither body creates its own Section, so there is never a duplicate router panel,
 * title, or decision card on the page.
 */
export function RouterSection({ boot, mo, loading }: Props) {
  const [strategy, setStrategy] = useState<Strategy>("mo");

  return (
    <Section
      id="router"
      index="01"
      eyebrow="Live router"
      title="OptiRoute Router"
      lead={LEAD[strategy]}
    >
      <div className="router-switch">
        <span className="field-label" id="router-strategy">Routing strategy</span>
        <Segmented<Strategy>
          ariaLabel="Routing strategy"
          options={[
            { value: "mo", label: "Multi-Objective", title: "Default: balances quality, cost, latency and privacy" },
            { value: "legacy", label: "Research Baseline", title: "The validated legacy confidence cascade, for comparison" },
          ]}
          value={strategy}
          onChange={(v) => setStrategy(v)}
        />
      </div>

      {strategy === "mo" ? (
        <MoRouter boot={boot} mo={mo} loading={loading} />
      ) : (
        <RouteArena boot={boot} />
      )}
    </Section>
  );
}
