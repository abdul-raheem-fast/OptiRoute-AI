import { useEffect, useLayoutEffect, useState } from "react";
import { fmtUSD } from "../lib/format";
import type { ModelRow, RouteDecision } from "../lib/types";

const TIERS = ["easy", "medium", "hard"] as const;

/** True for the escalation reasons, which read as warnings rather than wins. */
function isRisk(reason: string, fallback: boolean): boolean {
  return fallback && (reason.startsWith("no model") || reason.startsWith("escalated"));
}

interface Props {
  decision: RouteDecision;
  models: ModelRow[];
}

export function DecisionPanel({ decision: d, models }: Props) {
  // Bars animate from 0 -> value on every new decision.
  const [grown, setGrown] = useState(false);
  const [pop, setPop] = useState(false);

  useLayoutEffect(() => {
    setGrown(false);
    setPop(false);
  }, [d]);

  useEffect(() => {
    const raf = requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        setGrown(true);
        setPop(true);
      })
    );
    return () => cancelAnimationFrame(raf);
  }, [d]);

  const t = d.threshold;
  const wns = d.why_not_strongest;
  const tierTop = d.tier_probs
    ? TIERS.reduce((best, k) => ((d.tier_probs?.[k] ?? 0) > (d.tier_probs?.[best] ?? 0) ? k : best), TIERS[0])
    : null;

  return (
    <>
      <div className="decision-top">
        <div>
          <span className="block-label" style={{ marginBottom: 6 }}>
            <span>Routed to</span>
          </span>
          <div className={`decision-model ${pop ? "is-pop" : ""}`}>{d.chosen_model}</div>
          <div className="decision-sub">
            <span>
              class: <strong>{d.query_class}</strong>
            </span>
            <span className="sep">&bull;</span>
            <span className="num">
              {fmtUSD(d.est_cost_per_query, 6)}/query vs GPT-5{" "}
              {fmtUSD(d.strongest_cost_per_query, 6)}
            </span>
            <span className="sep">&bull;</span>
            <span className="num">{fmtUSD(d.est_latency_s, 2)} est. latency</span>
            {d.is_fallback ? (
              <>
                <span className="sep">&bull;</span>
                <em>no model met the threshold — safety fallback to strongest</em>
              </>
            ) : null}
          </div>
        </div>

        <div className="decision-saving">
          <span className="big num">{d.est_saving_pct}%</span>
          <span className="cap">cheaper on this query</span>
        </div>
      </div>

      {d.tier_probs ? (
        <div className="decision-block">
          <div className="block-label">
            <span>Query complexity</span>
            <span className="tag">router-derived estimate</span>
          </div>
          <div className="cx-meter">
            {TIERS.map((k) => (
              <div
                key={k}
                className={`cx-cell ${tierTop === k ? "is-top" : ""}`}
                title={`P(${k}) = ${((d.tier_probs?.[k] ?? 0) * 100).toFixed(0)}%`}
              >
                <span className="k">{k}</span>
                <span className="v num">{((d.tier_probs?.[k] ?? 0) * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="decision-block">
        <div className="block-label">
          <span>P(correct) per model</span>
          <span className="tag">cheapest &rarr; strongest &middot; gate t = {t.toFixed(2)}</span>
        </div>
        <div className="probrows">
          {models.map((m) => {
            const p = d.p_correct[m.model] ?? 0;
            const chosen = m.model === d.chosen_model;
            return (
              <div key={m.model} className={`probrow ${chosen ? "is-chosen" : ""} ${p >= t ? "is-over" : ""}`}>
                <span className="probrow-name" title={m.model}>
                  {m.model}
                </span>
                <span className="probrow-track">
                  <span
                    className="probrow-fill"
                    style={{ width: grown ? `${(p * 100).toFixed(1)}%` : "0%" }}
                  />
                  <span className="gate" style={{ left: `${(t * 100).toFixed(1)}%` }} />
                </span>
                <span className="probrow-val">{(p * 100).toFixed(1)}%</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="decision-block">
        <div className="block-label">
          <span>Cascade walk</span>
          <span className="tag">threshold t = {t.toFixed(2)}</span>
        </div>
        <div className="cascade">
          {d.cascade_trace.map((s, i) => (
            <span key={`${s.model}-${i}`} style={{ display: "contents" }}>
              {i > 0 ? (
                <span className="cstep-arrow" style={{ animationDelay: `${i * 70}ms` }}>
                  &rarr;
                </span>
              ) : null}
              <span
                className={`cstep ${s.passes ? "is-accept" : "is-reject"}`}
                style={{ animationDelay: `${i * 70}ms` }}
              >
                <span className="m">{s.model}</span>
                <span className="p">
                  p={(s.p_correct * 100).toFixed(1)}% {s.passes ? "\u2713 take" : "\u2717 below t"}
                </span>
              </span>
            </span>
          ))}
          {d.is_fallback ? (
            <>
              <span
                className="cstep-arrow"
                style={{ animationDelay: `${d.cascade_trace.length * 70}ms` }}
              >
                &rarr;
              </span>
              <span
                className="cstep is-accept"
                style={{ animationDelay: `${(d.cascade_trace.length + 1) * 70}ms` }}
              >
                <span className="m">{d.chosen_model}</span>
                <span className="p">fallback: strongest</span>
              </span>
            </>
          ) : null}
        </div>
      </div>

      <div className="decision-block">
        <div className="block-label">
          <span>Why this route</span>
        </div>
        <ul className="why-list">
          {(d.reasons ?? []).map((r, i) => (
            <li key={i} className={isRisk(r, d.is_fallback) ? "is-risk" : ""}>
              {r}
            </li>
          ))}
        </ul>
      </div>

      <div className="callout">
        Alternative: always-GPT-5 at <strong>{fmtUSD(d.strongest_cost_per_query, 6)}</strong>/query.
        This route costs {fmtUSD(d.est_cost_per_query, 6)} —{" "}
        <strong>you save {d.est_saving_pct}%</strong> on this query.
        <span className="fine">
          {wns?.verdict}
          {wns ? ` (+${wns.delta_accuracy_pts} pts expected quality for +${fmtUSD(wns.delta_cost_per_query, 5)}).` : ""}
        </span>
      </div>

      <p className="note" style={{ marginTop: "var(--s4)" }}>
        Cost and latency shown for arbitrary queries are benchmark averages of the chosen
        model, not a live meter. Headline savings come from the measured test split below.
      </p>
    </>
  );
}
