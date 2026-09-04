import { Card, CardTitle, Pill, Section } from "./ui";
import { ParetoFrontier } from "./ParetoFrontier";
import { PrivacyPanel } from "./PrivacyPanel";
import { fmtLatency, fmtUSD } from "../lib/format";
import type { MoEvalRow, ResultsPayload } from "../lib/types";
import type { MultiObjective } from "../lib/api";

/**
 * The honest evidence for the multi-objective claim:
 *   1. the model-level Pareto frontier (measured train-split quality/cost/latency);
 *   2. the sealed-test tradeoff table - every routing objective measured against
 *      always-cheapest / always-GPT-5 / the legacy cascade (COST x QUALITY x
 *      LATENCY x PRIVACY), from routing/results/mo_eval_report.csv;
 *   3. the privacy policy and per-model metadata that gate eligibility.
 *
 * No number here is invented: the chart reads /api/pareto, the table reads the
 * frozen evaluation CSV, and the privacy grid reads /api/privacy.
 */

function signed(v: number, digits = 1, suffix = ""): string {
  const s = v > 0 ? "+" : "";
  return `${s}${v.toFixed(digits)}${suffix}`;
}

function TradeoffTable({ rows }: { rows: MoEvalRow[] }) {
  const order = [
    "always-cheapest", "always-gpt-5", "legacy-cascade",
    "mo-economy", "mo-balanced", "mo-speed", "mo-quality", "mo-private",
  ];
  const sorted = [...rows].sort((a, b) => {
    const ia = order.findIndex((o) => a.policy.startsWith(o));
    const ib = order.findIndex((o) => b.policy.startsWith(o));
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  return (
    <div className="table-wrap">
      <table className="table table--tight">
        <thead>
          <tr>
            <th>Policy (sealed test)</th>
            <th>Accuracy</th>
            <th>Quality vs GPT-5</th>
            <th>Cost / query</th>
            <th>Cost cut</th>
            <th>Latency</th>
            <th>p95</th>
            <th>Latency Δ</th>
            <th>Privacy-filtered</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const isLegacy = r.policy.startsWith("legacy");
            const isMo = r.policy.startsWith("mo-");
            const cls = isLegacy ? "is-legacy-row" : isMo ? "is-mo-row" : "";
            return (
              <tr key={r.policy} className={cls}>
                <td className="text" style={{ fontWeight: 600 }}>{r.policy}</td>
                <td className="num">{Number(r.accuracy_pct).toFixed(2)}%</td>
                <td className="num">{Number(r.quality_vs_gpt5_pct).toFixed(1)}%</td>
                <td className="num">{fmtUSD(Number(r.avg_cost_per_query), 6)}</td>
                <td className="num">{Number(r.cost_reduction_vs_gpt5_pct).toFixed(1)}%</td>
                <td className="num">{fmtLatency(Number(r.avg_latency_s))}</td>
                <td className="num">{fmtLatency(Number(r.p95_latency_s))}</td>
                <td className="num">{signed(Number(r.latency_delta_vs_gpt5_s), 2, " s")}</td>
                <td className="num">{Number(r.privacy_filtered_pct).toFixed(1)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface Props {
  mo: MultiObjective;
  results: ResultsPayload;
}

export function MoEvidence({ mo, results }: Props) {
  const pareto = mo.pareto;
  const privacy = mo.privacy;
  const evalRows = results.mo_eval_report ?? [];
  const approved = privacy?.deployment.approved_for_sensitive ?? [];

  return (
    <Section
      id="frontier"
      index="03"
      eyebrow="Pareto & privacy"
      title="Cost ↔ quality ↔ latency ↔ privacy"
      lead="Why the router picks what it picks: the measured model frontier, the sealed-test
            tradeoff for every objective, and the privacy policy that gates eligibility before
            any utility is computed."
    >
      <div className="mo-evidence">
        <Card variant="elevated">
          <CardTitle hint="measured train-split quality / cost / latency">
            Model Pareto frontier
          </CardTitle>
          {pareto ? (
            <>
              <ParetoFrontier points={pareto.points} frontiers={pareto.frontiers} approved={approved} />
              <p className="note" style={{ marginTop: "var(--s3)" }}>{pareto.note}</p>
            </>
          ) : (
            <p className="legend-empty">Pareto data unavailable (run python -m routing.tune_mo).</p>
          )}
        </Card>

        <Card variant="base">
          <CardTitle hint="routing/results/mo_eval_report.csv · sealed test split">
            Objective tradeoff — measured, not simulated
          </CardTitle>
          {evalRows.length ? (
            <>
              <TradeoffTable rows={evalRows} />
              <div className="tradeoff-legend">
                <span className="legend-item"><i className="legend-swatch is-legacy" /><span className="nm">legacy cascade (production default)</span></span>
                <span className="legend-item"><i className="legend-swatch is-mo" /><span className="nm">multi-objective (experimental)</span></span>
              </div>
              <p className="chart-caption">
                The legacy cascade stays binary (Qwen3-8B / GPT-5) because under its ~80% quality
                floor those two are the only economically admissible models — a measured finding,
                not a limitation hidden by the demo. The multi-objective router spreads traffic
                only where an objective genuinely rewards it (economy → cheap+fast models, speed →
                gemini-2.5-flash, private → local models). Sealed test split; tuned on train/val only.
              </p>
            </>
          ) : (
            <p className="legend-empty">
              Sealed-test MO report unavailable (run python -m routing.eval_mo).
            </p>
          )}
        </Card>

        {privacy ? (
          <Card variant="base" className="privacy-card">
            <CardTitle hint="filter runs before selection">Privacy</CardTitle>
            <PrivacyPanel privacy={privacy} />
          </Card>
        ) : null}
      </div>

      <div className="mo-status-line">
        <Pill tone="info">default router: {mo.objectives?.default_router ?? "legacy"}</Pill>
        <span className="note">
          The multi-objective router is exposed as an experimental mode. The legacy cascade remains
          the production default because it preserves the validated headline result; the objectives
          above trade cost, latency and privacy differently rather than dominating it on every axis.
        </span>
      </div>
    </Section>
  );
}
