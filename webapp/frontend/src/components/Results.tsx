import { FrontierChart } from "./FrontierChart";
import { Card, CardTitle, Pill, Section } from "./ui";
import { fmtUSD } from "../lib/format";
import type { PolicyRow } from "../lib/types";

function floorMet(r: PolicyRow): boolean {
  return r.meets_quality_floor === true || String(r.meets_quality_floor) === "True";
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
          Cost is the objective; quality is the constraint. OptiRoute optimizes spend
          subject to a measured quality floor — it is <b>not</b> “send everything to the
          cheapest model”.
        </p>
      </div>
    </Card>
  );
}

export function Results({ rows }: { rows: PolicyRow[] }) {
  return (
    <Section
      id="results"
      index="04"
      eyebrow="Measured results"
      title="Frozen numbers from the committed pipeline"
      lead="Official held-out test split, stratified by capability class and difficulty
            tier. Nothing on this page is estimated — these rows are the pipeline output."
    >
      <div className="grid grid-2">
        <Card variant="elevated">
          <CardTitle hint="test split">Policy comparison</CardTitle>
          <PolicyTable rows={rows} />
          <p className="chart-caption">
            Floor: a policy must keep &ge;90% of always-strongest accuracy. Oracle =
            hindsight-optimal pick per query, the theoretical ceiling.
          </p>
        </Card>

        <Card variant="elevated">
          <CardTitle hint="up and to the left is better">Cost – accuracy frontier</CardTitle>
          <FrontierChart rows={rows} />
          <p className="chart-caption">
            Each point is a routing policy on the test split. The shaded band below the
            dashed line fails the quality floor.
          </p>
        </Card>
      </div>

      <Guardrail rows={rows} />
    </Section>
  );
}
