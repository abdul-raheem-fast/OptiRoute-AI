import { Section } from "./ui";
import { fmtUSD, shortClass } from "../lib/format";
import { modelColor } from "../lib/palette";
import type { ModelsPayload } from "../lib/types";

export function ModelPool({ models }: { models: ModelsPayload }) {
  const classes = models.classes;

  return (
    <Section
      id="models"
      index="06"
      eyebrow="The model pool"
      title="Eight models, ordered cheapest to strongest"
      lead="Per-model accuracy by capability class on the aligned benchmark, with registry
            pricing in USD per 1M tokens. The cascade always walks this order."
    >
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>Model</th>
              <th>Provider</th>
              <th>$/1M in / out</th>
              <th>Avg $/query</th>
              <th>Avg latency</th>
              {classes.map((c) => (
                <th key={c}>{shortClass(c)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {models.models.map((m, i) => {
              const priced = m.price_in != null && m.price_in > 0;
              return (
                <tr key={m.model}>
                  <td>
                    <i
                      className="legend-swatch"
                      style={{ background: modelColor(i), borderRadius: "50%" }}
                      title={`cascade position ${i + 1}`}
                    />
                  </td>
                  <td className="text" style={{ fontWeight: 600 }}>
                    {m.model}
                  </td>
                  <td className="text dim">{m.provider.split("/")[0].trim()}</td>
                  <td>{priced ? `${m.price_in?.toFixed(2)} / ${m.price_out?.toFixed(2)}` : "self-hosted"}</td>
                  <td>{fmtUSD(m.avg_cost_per_query, 6)}</td>
                  <td>{m.avg_latency_s.toFixed(3)} s</td>
                  {classes.map((c) => (
                    <td key={c}>{(m.class_accuracy[c] ?? 0).toFixed(1)}%</td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="chart-caption">
        Two self-hosted models (Llama-3.1-8B-Instruct, Qwen3-8B) carry zero marginal token
        cost, so their measured per-query cost is effectively 0 — that is where the savings
        come from when the router is confident.
      </p>
    </Section>
  );
}
