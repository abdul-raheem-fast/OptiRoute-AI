import { Section, StatTile } from "./ui";

/**
 * A compact, factual closing summary. Every item is a real project artifact, not a
 * marketing claim: the numbers come from the frozen benchmark/eval and the test suite,
 * and the qualitative points describe how the router actually behaves — a local decision
 * with no extra LLM call to route, Pareto-aware selection behind hard constraints, and a
 * validated cost-optimized cascade kept as an honest baseline.
 */
const PROOFS = [
  "Sealed test split — tuned on train/val, scored once.",
  "Local routing — no extra LLM call to route.",
  "Pareto-aware selection behind hard privacy and latency constraints.",
  "A validated, cost-optimized legacy baseline.",
];

export function WhatWeProved() {
  return (
    <Section
      id="proved"
      index="05"
      eyebrow="Bottom line"
      title="What we proved"
      lead="OptiRoute measures the quality, cost, latency and privacy trade-offs and lets you pick
            the operating point that fits — against a validated baseline."
    >
      <div className="stat-grid">
        <StatTile accent value="1,887" label="Benchmark queries, aligned across models" />
        <StatTile value="8" label="LLMs evaluated on the shared benchmark" />
        <StatTile value="5" label="Configurable routing policies (objectives)" />
        <StatTile value="130/130" label="Python tests passing" />
      </div>
      <ul className="proved-list">
        {PROOFS.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
    </Section>
  );
}
