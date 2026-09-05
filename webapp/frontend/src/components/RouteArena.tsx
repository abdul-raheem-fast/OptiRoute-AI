import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DecisionPanel } from "./DecisionPanel";
import { Card, EmptyState, Pill, Segmented } from "./ui";
import { routeQuery } from "../lib/api";
import { fmtUSD } from "../lib/format";
import { TIER_COLORS } from "../lib/palette";
import type { Bootstrap, RouteDecision } from "../lib/types";

/**
 * The legacy confidence cascade, kept as a scientifically useful BASELINE beside the
 * multi-objective default router. Self-contained: it owns its routing state so the parent
 * only passes the bootstrap payload. Walks cheapest-first and takes the first model whose
 * P(correct) clears the gate t, else escalates to the strongest — this is the frozen,
 * validated headline result (see the Results section).
 */
export function RouteArena({ boot }: { boot: Bootstrap }) {
  const [mode, setMode] = useState("balanced");
  const [threshold, setThreshold] = useState(0.95);
  const [query, setQuery] = useState("");
  const [queryClass, setQueryClass] = useState("");
  const [decision, setDecision] = useState<RouteDecision | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** One routing round-trip. Threshold is passed explicitly so callers that just
   *  changed it (mode switch, auto-route) never race stale state. */
  const run = useCallback(async (q: string, cls: string, t: number) => {
    const text = q.trim();
    if (!text) return;
    setBusy(true);
    setError(null);
    try {
      const d = await routeQuery({ query: text, query_class: cls || null, threshold: t });
      setDecision(d);
    } catch (e) {
      setDecision(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  // Open with a real benchmark query already routed through the balanced policy.
  const autoRan = useRef(false);
  useEffect(() => {
    if (autoRan.current) return;
    autoRan.current = true;
    const balanced = boot.modes.modes.find((m) => m.key === "balanced");
    const t = balanced?.t ?? boot.modes.t_star ?? 0.95;
    if (balanced) setMode(balanced.key);
    setThreshold(t);
    const first = boot.scenarios.scenarios[0];
    if (first) {
      setQuery(first.query);
      setQueryClass(first.query_class);
      void run(first.query, first.query_class, t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleMode = useCallback(
    (key: string) => {
      setMode(key);
      const preset = boot.modes.modes.find((m) => m.key === key);
      if (!preset) return;
      setThreshold(preset.t);
      if (query.trim()) void run(query, queryClass, preset.t);
    },
    [boot, query, queryClass, run]
  );

  const handleChallenge = useCallback(() => {
    const pool = boot.scenarios.challenges ?? [];
    if (!pool.length) return;
    let pick = pool[Math.floor(Math.random() * pool.length)];
    for (let g = 0; pick.query === query && g < 12; g++) {
      pick = pool[Math.floor(Math.random() * pool.length)];
    }
    setQuery(pick.query);
    setQueryClass(pick.query_class);
    void run(pick.query, pick.query_class, threshold);
  }, [boot, query, run, threshold]);

  const activeMode = useMemo(
    () => boot.modes.modes.find((m) => m.key === mode) ?? boot.modes.modes[0],
    [boot.modes.modes, mode]
  );

  const modeOptions = boot.modes.modes.map((m) => ({
    value: m.key,
    label: m.label,
    title: `${m.description} (t = ${m.t.toFixed(2)})`,
  }));

  return (
    <div className="arena">
      {/* ---------------------------------------------------- input column */}
      <Card variant="elevated" className="arena-input" as="div">
        <div>
          <span className="field-label">Routing policy</span>
          <Segmented ariaLabel="Routing policy" options={modeOptions} value={mode} onChange={handleMode} />
          {activeMode ? (
            <p className="mode-note" style={{ marginTop: "var(--s3)" }}>
              <b>
                {activeMode.label} (t = {activeMode.t.toFixed(2)})
              </b>{" "}
              — {activeMode.description}.{" "}
              {activeMode.val_accuracy_pct != null ? (
                <>
                  Measured on the {activeMode.measured_on}: {activeMode.val_accuracy_pct.toFixed(1)}%
                  accuracy at {fmtUSD(activeMode.val_avg_cost_per_query ?? 0, 4)}/query.{" "}
                </>
              ) : null}
              {activeMode.meets_floor ? (
                <Pill tone="ok">clears quality floor</Pill>
              ) : (
                <Pill tone="warn">below quality floor</Pill>
              )}
            </p>
          ) : null}
        </div>

        <div>
          <label className="field-label" htmlFor="arena-query">Query</label>
          <textarea
            id="arena-query"
            className="textarea"
            rows={5}
            value={query}
            placeholder="Click a real benchmark query below, or type your own."
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) void run(query, queryClass, threshold);
            }}
          />
        </div>

        <div className="arena-row">
          <div>
            <label className="field-label" htmlFor="arena-class">Capability class</label>
            <select id="arena-class" className="select" value={queryClass} onChange={(e) => setQueryClass(e.target.value)}>
              <option value="">auto-detect (heuristic)</option>
              {boot.models.classes.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <div className="threshold-row">
              <label className="field-label" htmlFor="arena-t" style={{ margin: 0 }}>Confidence threshold</label>
              <span className="threshold-value">t = {threshold.toFixed(2)}</span>
            </div>
            <input
              id="arena-t"
              type="range" min={0.5} max={0.99} step={0.01} value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              onMouseUp={() => { if (query.trim()) void run(query, queryClass, threshold); }}
              onTouchEnd={() => { if (query.trim()) void run(query, queryClass, threshold); }}
            />
          </div>
        </div>

        <div className="arena-actions">
          <button
            type="button" className="btn btn--primary"
            onClick={() => void run(query, queryClass, threshold)} disabled={busy || !query.trim()}
          >
            {busy ? "Routing…" : "Route it"}
          </button>
          <button
            type="button" className="btn btn--ghost" onClick={handleChallenge}
            disabled={busy || !boot.scenarios.challenges.length} title="Load a random real benchmark query"
          >
            &#9889; Challenge the router
          </button>
        </div>

        <div>
          <div className="scenario-strip">
            <span className="field-label">Real benchmark queries:</span>
            {boot.scenarios.scenarios.map((s) => (
              <button
                key={s.label}
                type="button"
                className="chip"
                title={`${s.query_class} — expected: ${s.expected_route === "cheap" ? "cheap route" : "escalate to strongest"}`}
                onClick={() => {
                  setQuery(s.query);
                  setQueryClass(s.query_class);
                  void run(s.query, s.query_class, threshold);
                }}
              >
                <i
                  className="dot"
                  style={{ background: TIER_COLORS[s.dot] ?? TIER_COLORS.medium, color: TIER_COLORS[s.dot] ?? TIER_COLORS.medium }}
                />
                {s.label}
              </button>
            ))}
          </div>
          <p className="note" style={{ marginTop: "var(--s3)" }}>Source: {boot.scenarios.source}.</p>
        </div>
      </Card>

      {/* -------------------------------------------------- decision column */}
      <Card variant="hero">
        {error ? (
          <EmptyState glyph="!" title="Routing failed" body={error} />
        ) : decision ? (
          <DecisionPanel decision={decision} models={boot.models.models} />
        ) : (
          <EmptyState
            glyph="◎"
            title="The cascade decision appears here"
            body="Per-model confidence, the cheapest-first cascade walk against t, the reasoning,
                  and what this query saves versus GPT-5."
          />
        )}
      </Card>
    </div>
  );
}
