import { useState } from "react";
import { Card, CardTitle, Pill } from "./ui";
import { classifySensitivity } from "../lib/api";
import type { PrivacyPayload, SensitivityResult } from "../lib/types";

/**
 * Privacy metadata + the LOCAL sensitivity classifier.
 *
 * Everything shown here comes from webapp/privacy_policy.json via /api/privacy
 * and /api/sensitivity. No provider guarantee is fabricated: external models
 * report data_retention = "administrator-configured", and the provenance line
 * makes that explicit. The classifier is deterministic and runs in-process -
 * no query is ever sent to an external LLM to decide its sensitivity.
 */

function SensitivityDemo() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<SensitivityResult | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    const q = text.trim();
    if (!q) return;
    setBusy(true);
    try {
      setResult(await classifySensitivity(q));
    } catch {
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sens-demo">
      <label className="field-label" htmlFor="sens-input">
        Try the local sensitivity classifier
      </label>
      <div className="sens-row">
        <input
          id="sens-input"
          className="input"
          value={text}
          placeholder="e.g. 'My email is jane@hospital.org' or 'explain quicksort'"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void run();
          }}
        />
        <button type="button" className="btn btn--ghost" onClick={() => void run()} disabled={busy || !text.trim()}>
          {busy ? "Checking…" : "Classify"}
        </button>
      </div>
      {result ? (
        <div className="sens-result">
          <Pill tone={result.sensitivity === "sensitive" ? "warn" : "ok"}>{result.sensitivity}</Pill>
          <span className="note">{result.reason}</span>
        </div>
      ) : null}
      <p className="note">
        Deterministic regex + keyword rules evaluated in-process. No raw query text is stored or
        sent to any model to make this decision.
      </p>
    </div>
  );
}

export function PrivacyPanel({ privacy }: { privacy: PrivacyPayload }) {
  const dep = privacy.deployment;
  const models = Object.entries(privacy.models);
  const prov = privacy.provenance;

  return (
    <div className="privacy-grid">
      <Card variant="elevated">
        <CardTitle hint="webapp/privacy_policy.json">Deployment policy</CardTitle>
        <div className="policy-flags">
          <div className="line">
            <span>allow external models</span>
            <Pill tone={dep.allow_external_models ? "info" : "warn"}>
              {dep.allow_external_models ? "yes" : "no"}
            </Pill>
          </div>
          <div className="line">
            <span>allow sensitive queries</span>
            <Pill tone={dep.allow_sensitive_queries ? "info" : "warn"}>
              {dep.allow_sensitive_queries ? "yes" : "no"}
            </Pill>
          </div>
          <div className="line">
            <span>approved for sensitive</span>
            <b className="mono">{dep.approved_for_sensitive.join(", ") || "none"}</b>
          </div>
          <div className="line">
            <span>sensitivity rules</span>
            <b>{privacy.sensitivity_rules.n_patterns} patterns + {privacy.sensitivity_rules.keywords.length} keywords</b>
          </div>
        </div>
        <div className="callout" style={{ marginTop: "var(--s4)" }}>
          {privacy.note}
        </div>
        {typeof prov === "object" && prov ? (
          <p className="note" style={{ marginTop: "var(--s3)" }}>
            Provenance — retention: <b>{(prov as Record<string, string>).data_retention}</b>
          </p>
        ) : null}
        <div style={{ marginTop: "var(--s4)" }}>
          <SensitivityDemo />
        </div>
      </Card>

      <Card variant="base">
        <CardTitle hint="no fabricated guarantees">Per-model privacy metadata</CardTitle>
        <div className="table-wrap">
          <table className="table table--tight">
            <thead>
              <tr>
                <th>Model</th>
                <th>Level</th>
                <th>External API</th>
                <th>Local</th>
                <th>Data retention</th>
                <th>Sensitive-OK</th>
              </tr>
            </thead>
            <tbody>
              {models.map(([name, meta]) => (
                <tr key={name}>
                  <td className="text" style={{ fontWeight: 600 }}>{name}</td>
                  <td className="dim">{meta.privacy_level}</td>
                  <td>{meta.external_api ? "yes" : "no"}</td>
                  <td>{meta.locally_hosted ? "yes" : "no"}</td>
                  <td className="dim">{meta.data_retention}</td>
                  <td>
                    <Pill tone={meta.approved_for_sensitive ? "ok" : "bad"}>
                      {meta.approved_for_sensitive ? "approved" : "not approved"}
                    </Pill>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note" style={{ marginTop: "var(--s3)" }}>
          The privacy filter runs BEFORE model selection: a model not approved for a sensitive
          query can never be chosen, whatever its utility. "Local routing" means the routing
          decision needs no extra LLM call — it does not by itself make the selected model private.
        </p>
      </Card>
    </div>
  );
}
