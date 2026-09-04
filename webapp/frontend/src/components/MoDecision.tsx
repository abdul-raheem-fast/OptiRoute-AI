import { fmtLatency, fmtUSD } from "../lib/format";
import { modelColor } from "../lib/palette";
import { Pill } from "./ui";
import type { MoRouteDecision } from "../lib/types";

/**
 * The multi-objective decision, rendered honestly:
 *   - the score is CALIBRATED (Platt, fit on train, verified on val) and is
 *     labelled "routing score", never a raw probability claim;
 *   - estimated cost/latency are the chosen model's MEASURED benchmark averages;
 *   - latency is split into router overhead / model inference / end-to-end;
 *   - privacy status and the binding constraint are always visible.
 */

const MODEL_ORDER = [
  "Llama-3.1-8B-Instruct", "Qwen3-8B", "deepseek-v3-0324", "gemini-2.5-flash",
  "gpt-4.1", "claude-sonnet-4", "gemini-2.5-pro", "gpt-5",
];

function LatencyParts({ d }: { d: MoRouteDecision }) {
  const l = d.latency;
  return (
    <div className="lat-parts">
      <div className="lat-part">
        <span className="k">router overhead</span>
        <span className="v num">{l.router_overhead_ms.toFixed(1)} ms</span>
      </div>
      <span className="lat-plus">+</span>
      <div className="lat-part">
        <span className="k">model inference</span>
        <span className="v num">{l.model_inference_ms.toFixed(0)} ms</span>
      </div>
      <span className="lat-plus">=</span>
      <div className="lat-part is-total">
        <span className="k">end-to-end</span>
        <span className="v num">{l.end_to_end_ms.toFixed(0)} ms</span>
      </div>
    </div>
  );
}

export function MoDecision({ d }: { d: MoRouteDecision }) {
  const blocked = d.selected_model == null;

  return (
    <>
      <div className="decision-top">
        <div>
          <span className="block-label" style={{ marginBottom: 6 }}>
            <span>Selected model</span>
            <span className="tag">{d.mode_label} objective</span>
          </span>
          <div className="decision-model">{blocked ? "— none —" : d.selected_model}</div>
          <div className="decision-sub">
            <span>
              class: <strong>{d.query_class}</strong>
            </span>
            <span className="sep">&bull;</span>
            <Pill tone={d.privacy_status === "approved" ? "ok" : "bad"}>
              privacy: {d.privacy_status}
            </Pill>
            <span className="sep">&bull;</span>
            <Pill tone={d.sensitive ? "warn" : "info"}>
              query: {d.sensitivity.sensitivity}
            </Pill>
            {d.is_fallback ? (
              <>
                <span className="sep">&bull;</span>
                <em>escalated to strongest eligible</em>
              </>
            ) : null}
          </div>
        </div>
        {!blocked ? (
          <div className="decision-saving">
            <span className="big num">{((d.routing_score ?? 0) * 100).toFixed(1)}%</span>
            <span className="cap">routing score (calibrated)</span>
          </div>
        ) : null}
      </div>

      {blocked ? (
        <div className="callout callout--warn">
          <b>Nothing was routed.</b> {d.reason}
        </div>
      ) : (
        <>
          <div className="mo-metrics">
            <div className="mo-metric">
              <span className="k">est. cost / query</span>
              <span className="v num">{fmtUSD(d.estimated_cost_per_query, 6)}</span>
              <span className="sub">vs GPT-5 {fmtUSD(d.strongest_cost_per_query, 6)}</span>
            </div>
            <div className="mo-metric">
              <span className="k">est. model latency</span>
              <span className="v num">{fmtLatency((d.estimated_latency_ms ?? 0) / 1000)}</span>
              <span className="sub">measured benchmark average</span>
            </div>
            <div className="mo-metric">
              <span className="k">savings vs GPT-5</span>
              <span className="v num">{(d.est_saving_pct ?? 0).toFixed(1)}%</span>
              <span className="sub">on this query</span>
            </div>
          </div>

          <div className="decision-block">
            <div className="block-label">
              <span>Latency budget</span>
              <span className="tag">router overhead is measured live</span>
            </div>
            <LatencyParts d={d} />
          </div>

          <div className="decision-block">
            <div className="block-label">
              <span>Why this route</span>
              <span className="tag mono">{d.reason_code}</span>
            </div>
            <p className="mo-reason">{d.reason}</p>
            <div className="constraint-chips">
              <span className="cchip">
                λ<sub>cost</sub> = {d.constraints.lambda_cost}
              </span>
              <span className="cchip">
                λ<sub>latency</sub> = {d.constraints.lambda_latency}
              </span>
              <span className="cchip">
                quality floor:{" "}
                {d.constraints.quality_floor != null ? d.constraints.quality_floor.toFixed(2) : "off (mode target)"}
              </span>
              <span className="cchip">
                latency budget:{" "}
                {d.constraints.latency_budget_ms != null
                  ? `${d.constraints.latency_budget_ms.toFixed(0)} ms${
                      d.constraints.latency_budget_met === false ? " (unmet → fastest)" : ""
                    }`
                  : "none"}
              </span>
              {d.constraints.privacy_restricted ? <span className="cchip is-on">privacy-restricted</span> : null}
            </div>
          </div>

          {d.why_not_strongest ? (
            <div className="callout">
              Strongest eligible model: <b>{d.why_not_strongest.strongest_model}</b>.{" "}
              {d.why_not_strongest.verdict}.
              <span className="fine">
                {" "}
                (+{d.why_not_strongest.delta_quality_pts} pts calibrated quality for +
                {fmtUSD(d.why_not_strongest.delta_cost_per_query, 6)}/query.)
              </span>
            </div>
          ) : null}

          {d.pareto ? (
            <div className="decision-block">
              <div className="block-label">
                <span>Pareto status</span>
              </div>
              <p className="note">
                {d.selected_model} is{" "}
                <b>{d.pareto.on_frontier.length ? `on: ${d.pareto.on_frontier.join(", ")}` : "not on a frontier"}</b>.
                {d.pareto.is_strongest_eligible ? " It is also the strongest eligible model here." : ""}
              </p>
            </div>
          ) : null}

          {d.model_scores && d.model_scores.length ? (
            <div className="decision-block">
              <div className="block-label">
                <span>Model comparison</span>
                <span className="tag">eligible frontier under this objective</span>
              </div>
              <div className="table-wrap">
                <table className="table table--tight">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>Routing score</th>
                      <th>Utility</th>
                      <th>Eligible</th>
                      <th>Admissible</th>
                      <th>Measured cost</th>
                      <th>Measured latency</th>
                      <th>Frontier</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...d.model_scores]
                      .sort((a, b) => MODEL_ORDER.indexOf(a.model) - MODEL_ORDER.indexOf(b.model))
                      .map((m, i) => {
                        const chosen = m.model === d.selected_model;
                        return (
                          <tr key={m.model} className={chosen ? "is-chosen-row" : ""}>
                            <td className="text" style={{ fontWeight: chosen ? 700 : 500 }}>
                              <i
                                className="legend-swatch"
                                style={{ background: modelColor(MODEL_ORDER.indexOf(m.model)), borderRadius: "50%", marginRight: 6 }}
                              />
                              {m.model}
                              {chosen ? "  ✓" : ""}
                            </td>
                            <td className="num">{(m.routing_score * 100).toFixed(1)}%</td>
                            <td className="num">{m.utility.toFixed(3)}</td>
                            <td>{m.eligible ? "✓" : "—"}</td>
                            <td>{m.admissible ? "✓" : "—"}</td>
                            <td className="num">{fmtUSD(m.measured_cost_per_query, 6)}</td>
                            <td className="num">{fmtLatency(m.measured_latency_ms / 1000)}</td>
                            <td>{m.on_global_frontier ? "✓" : "—"}</td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </>
      )}

      <p className="note" style={{ marginTop: "var(--s4)" }}>
        The routing decision is pure local featurization + arithmetic — no model API is called to
        route. {d.privacy_note ?? ""}
      </p>
    </>
  );
}
