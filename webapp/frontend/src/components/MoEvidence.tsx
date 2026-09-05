import { Card, CardTitle, Collapsible, Pill, Section } from "./ui";
import { FrontierChart } from "./FrontierChart";
import { ParetoFrontier } from "./ParetoFrontier";
import { PrivacyPanel } from "./PrivacyPanel";
import { fmtLatency, fmtUSD } from "../lib/format";
import type { MoEvalRow, PolicyRow, ResultsPayload } from "../lib/types";
import type { MultiObjective } from "../lib/api";

/**
 * The single "Measured results" section: the honest evidence for the whole claim.
 *   • visible  — model Pareto frontier + sealed-test objective tradeoff table;
 *   • folded   — legacy baselines / cost-accuracy frontier / quality guardrail,
 *                and the privacy policy that gates eligibility before selection.
 *
 * No number here is invented: the chart reads /api/pareto, the tables read the
 * frozen evaluation CSVs, and the privacy grid reads /api/privacy.
 */

function signed(v: number, digits = 1, suffix = ""): string {
  const s = v > 0 ? "+" : "";
  return `${s}${v.toFixed(digits)}${suffix}`;
}

function floorMet(r: PolicyRow): boolean {
  return r.meets_quality_floor === true || String(r.meets_quality_floor) === "True";
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

function PolicyTable({ rows }: { rows: PolicyRow[] }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Policy</th>
            <th>Accuracy</th>
            <th>Quality vs GPT-5</th>
            <th>Cost / query</th>
            <th>Cost cut</th>
            <th>Floor</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const us = r.policy.startsWith("learned");
            const dim = r.policy === "always-cheapest" || r.policy === "random";
            return (
              <tr key={r.policy} className={`${us ? "is-us" : ""} ${dim ? "is-dim" : ""}`.trim()}>
                <td className="text">{r.policy}</td>
                <td>{Number(r.accuracy_pct).toFixed(2)}%</td>
                <td>{Number(r.quality_vs_strongest_pct).toFixed(1)}%</td>
                <td>{fmtUSD(Number(r.avg_cost_per_query), 6)}</td>
                <td>{Number(r.cost_reduction_vs_strongest_pct).toFixed(1)}%</td>
                <td>
                  <span className={floorMet(r) ? "yes" : "no"}>
                    {floorMet(r) ? "\u2713" : "\u2717"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Guardrail({ rows }: { rows: PolicyRow[] }) {
  const strongest = rows.find((r) => r.policy === "always-strongest");
  const learned = rows.find((r) => r.policy.startsWith("learned"));
  if (!strongest || !learned) return null;

  const floor = Number(strongest.accuracy_pct) * 0.9;
  const acc = Number(learned.accuracy_pct);
  const margin = acc - floor;
  const safe = margin >= 0;

  return (
    <Card variant="elevated" style={{ marginTop: "var(--grid-gap)" }}>
      <CardTitle hint="quality is the constraint, cost is the objective">
        Quality guardrail / SLO
      </CardTitle>
      <div className="guardrail">
        <div className="g-cell">
          <span className="v num">
            {floor.toFixed(1)}
            <small>%</small>
          </span>
          <span className="k">target quality floor</span>
        </div>
        <div className="g-cell">
          <span className="v num">
            {acc.toFixed(2)}
            <small>%</small>
          </span>
          <span className="k">current policy (test split)</span>
        </div>
        <div className="g-cell">
          <span className="v num">
            {margin >= 0 ? "+" : ""}
            {margin.toFixed(2)}
            <small> pts</small>
          </span>
          <span className="k">margin above floor</span>
        </div>
        <div className="g-cell g-cell--status">
          <Pill tone={safe ? "ok" : "bad"}>{safe ? "\u2713 SAFE" : "\u2717 AT RISK"}</Pill>
        </div>
        <p className="g-line">
          Cost is the objective; quality is the constraint — OptiRoute is <b>not</b> “send
          everything to the cheapest model”.
        </p>
      </div>
    </Card>
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
  const policyRows = results.baselines_report ?? [];
  const approved = privacy?.deployment.approved_for_sensitive ?? [];

  return (
    <Section
      id="results"
      index="02"
      eyebrow="Measured results"
      title="Every objective, measured on the sealed test split"
      lead="Nothing simulated — the frontier reads /api/pareto, the tables read the frozen evaluation
            CSVs. Tuned on train/val; the test split stayed sealed until final scoring."
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
          <CardTitle hint="routing/results/mo_eval_report.csv · sealed test">
            Objective tradeoff — measured, not simulated
          </CardTitle>
          {evalRows.length ? (
            <>
              <TradeoffTable rows={evalRows} />
              <div className="tradeoff-legend">
                <span className="legend-item"><i className="legend-swatch is-legacy" /><span className="nm">legacy cascade (validated baseline)</span></span>
                <span className="legend-item"><i className="legend-swatch is-mo" /><span className="nm">multi-objective (default experience)</span></span>
              </div>
              <p className="chart-caption">
                The legacy cascade concentrates on Qwen3-8B and GPT-5 because the pool's economic
                Pareto frontier is sparse — under its quality floor those are the only admissible
                models. An empirical finding, not a bug.
              </p>
            </>
          ) : (
            <p className="legend-empty">
              Sealed-test MO report unavailable (run python -m routing.eval_mo).
            </p>
          )}
        </Card>
      </div>

      <Collapsible title="Legacy baselines & quality guardrail" hint="the original cascade result">
        <div className="grid grid-2">
          <Card variant="elevated">
            <CardTitle hint="test split">Policy comparison</CardTitle>
            <PolicyTable rows={policyRows} />
            <p className="chart-caption">
              Floor: a policy must keep &ge;90% of always-strongest accuracy. Oracle = hindsight-optimal
              pick per query, the theoretical ceiling.
            </p>
          </Card>
          <Card variant="elevated">
            <CardTitle hint="up and to the left is better">Cost – accuracy frontier</CardTitle>
            <FrontierChart rows={policyRows} />
          </Card>
        </div>
        <Guardrail rows={policyRows} />
      </Collapsible>

      {privacy ? (
        <Collapsible title="Privacy policy & sensitivity filter" hint="runs before selection">
          <PrivacyPanel privacy={privacy} />
        </Collapsible>
      ) : null}

      <div className="mo-status-line">
        <Pill tone="info">default experience: multi-objective</Pill>
        <span className="note">
          Multi-objective is the default experience; the legacy cascade is the validated baseline and
          the API default. No single objective dominates on every axis — the table above is the
          honest head-to-head.
        </span>
      </div>
    </Section>
  );
}
