import { useMemo, useState } from "react";
import { Card, CardTitle, Section } from "./ui";
import { clamp, fmtInt, fmtUSD } from "../lib/format";
import type { PolicyRow } from "../lib/types";

const DAYS_PER_YEAR = 365;
const DAYS_PER_MONTH = 30.44;

export function BusinessImpact({ rows }: { rows: PolicyRow[] }) {
  const learned = rows.find((r) => r.policy.startsWith("learned"));
  const strongest = rows.find((r) => r.policy === "always-strongest");
  const options = useMemo(
    () =>
      rows.filter(
        (r) => !r.policy.startsWith("learned") && r.policy !== "oracle" && r.policy !== "random"
      ),
    [rows]
  );

  const [volume, setVolume] = useState(10000);
  const [strategy, setStrategy] = useState("always-strongest");

  const calc = useMemo(() => {
    if (!learned || !strongest) return null;
    const n = clamp(Math.round(volume) || 1, 1, 1_000_000);
    const baseRow = rows.find((r) => r.policy === strategy) ?? strongest;
    const base = Number(baseRow.avg_cost_per_query);
    const routed = Number(learned.avg_cost_per_query);
    const strong = Number(strongest.avg_cost_per_query);
    const yearBase = base * n * DAYS_PER_YEAR;
    const yearRouted = routed * n * DAYS_PER_YEAR;
    const saved = yearBase - yearRouted;
    return {
      n,
      basePolicy: baseRow.policy,
      baseDay: base * n,
      baseMonth: (yearBase / DAYS_PER_YEAR) * DAYS_PER_MONTH,
      baseYear: yearBase,
      routedDay: routed * n,
      routedMonth: (yearRouted / DAYS_PER_YEAR) * DAYS_PER_MONTH,
      routedYear: yearRouted,
      saved,
      cut: base > 0 ? (1 - routed / base) * 100 : 0,
      extraRoutedM: routed > 0 ? saved / routed / 1e6 : 0,
      extraStrong: strong > 0 ? Math.round(saved / strong) : 0,
      quality: Number(learned.quality_vs_strongest_pct),
    };
  }, [learned, strongest, rows, strategy, volume]);

  if (!calc) return null;

  return (
    <Section
      id="impact"
      index="04"
      eyebrow="Business impact"
      title="What the routing decision is worth"
      lead="Projection from measured per-query averages on the test split: your current
            strategy versus the OptiRoute learned cascade, at your traffic volume."
    >
      <div className="impact">
        <Card variant="elevated" className="impact-inputs">
          <div>
            <label className="field-label" htmlFor="impact-volume">
              Queries per day
            </label>
            <div className="volume-row">
              <input
                id="impact-volume"
                className="input"
                type="number"
                min={1}
                max={1000000}
                step={1}
                value={calc.n}
                onChange={(e) => setVolume(Number(e.target.value))}
              />
              <input
                type="range"
                min={2}
                max={6}
                step={0.1}
                aria-label="Queries per day (log scale)"
                value={Math.log10(calc.n)}
                onChange={(e) => setVolume(Math.round(Math.pow(10, Number(e.target.value))))}
              />
            </div>
          </div>

          <div>
            <label className="field-label" htmlFor="impact-strategy">
              Current strategy
            </label>
            <select
              id="impact-strategy"
              className="select"
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
            >
              {options.map((r) => (
                <option key={r.policy} value={r.policy}>
                  {r.policy}
                </option>
              ))}
            </select>
          </div>

          <p className="note">
            Drag for scale: 100 &rarr; 1,000,000 queries/day. Per-query costs are measured
            test-split averages of each policy — {fmtUSD(calc.routedDay / calc.n, 6)} routed
            vs {fmtUSD(calc.baseDay / calc.n, 6)} for <b>{calc.basePolicy}</b>.
          </p>
        </Card>

        <div>
          <div className="savings-hero">
            <div>
              <span className="k">Annual savings</span>
              <span className="savings-value num">{fmtUSD(calc.saved)}</span>
            </div>
            <div className="side">
              <span className="m num">{calc.cut.toFixed(1)}% lower spend</span>
              <span className="c">at {calc.quality.toFixed(1)}% of flagship quality</span>
              <span className="c">{fmtInt(calc.n)} queries / day</span>
            </div>
          </div>

          <div className="ledger" style={{ marginTop: "var(--grid-gap)" }}>
            <div className="ledger-group">Without OptiRoute AI · {calc.basePolicy}</div>
            <div className="ledger-row">
              <span className="k">Daily</span>
              <span className="v">{fmtUSD(calc.baseDay)}</span>
            </div>
            <div className="ledger-row">
              <span className="k">Monthly</span>
              <span className="v">{fmtUSD(calc.baseMonth)}</span>
            </div>
            <div className="ledger-row">
              <span className="k">Yearly</span>
              <span className="v">{fmtUSD(calc.baseYear)}</span>
            </div>

            <div className="ledger-group">With OptiRoute AI · learned cascade</div>
            <div className="ledger-row">
              <span className="k">Daily</span>
              <span className="v">{fmtUSD(calc.routedDay)}</span>
            </div>
            <div className="ledger-row">
              <span className="k">Monthly</span>
              <span className="v">{fmtUSD(calc.routedMonth)}</span>
            </div>
            <div className="ledger-row">
              <span className="k">Yearly</span>
              <span className="v">{fmtUSD(calc.routedYear)}</span>
            </div>
          </div>

          <Card className="reinvest">
            <CardTitle hint="same workload, same quality floor">What the savings buy</CardTitle>
            <ul>
              <li>
                <b>{calc.extraRoutedM.toFixed(1)}M</b> additional routed queries per year
              </li>
              <li>
                <b>{fmtInt(calc.extraStrong)}</b> extra GPT-5 queries for genuinely hard work
              </li>
              <li>
                <b>{calc.cut.toFixed(1)}%</b> lower inference spend on this workload
              </li>
              <li>fewer unnecessary high-compute calls — quality floor held at 90% of flagship</li>
            </ul>
          </Card>
        </div>
      </div>
    </Section>
  );
}
