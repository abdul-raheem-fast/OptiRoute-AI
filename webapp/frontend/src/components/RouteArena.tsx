import { useMemo } from "react";
import { DecisionPanel } from "./DecisionPanel";
import { Card, CardTitle, EmptyState, Pill, Section, Segmented, Skeleton } from "./ui";
import { fmtUSD } from "../lib/format";
import { modelColor, TIER_COLORS } from "../lib/palette";
import type { Bootstrap, RouteDecision, StatsPayload } from "../lib/types";

interface Props {
  boot: Bootstrap;
  stats: StatsPayload | null;
  mode: string;
  onMode: (key: string) => void;
  threshold: number;
  onThreshold: (t: number) => void;
  query: string;
  onQuery: (q: string) => void;
  queryClass: string;
  onQueryClass: (c: string) => void;
  decision: RouteDecision | null;
  busy: boolean;
  error: string | null;
  onRoute: () => void;
  /** Route a specific query immediately (scenario chips, challenge picks). */
  onRouteWith: (query: string, queryClass: string) => void;
  onChallenge: () => void;
}

/** Stacked bar of the demo session's routing distribution. */
function SessionBar({ boot, stats }: { boot: Bootstrap; stats: StatsPayload }) {
  const total = Math.max(1, stats.session_queries);
  const segments = boot.models.models
    .map((m, i) => ({ model: m.model, n: stats.distribution[m.model] ?? 0, color: modelColor(i) }))
    .filter((s) => s.n > 0);

  if (!segments.length) {
    return <p className="legend-empty">Route a query to start the session tally.</p>;
  }

  return (
    <>
      <div className="distbar" role="img" aria-label="Routing distribution this session">
        {segments.map((s) => (
          <span
            key={s.model}
            style={{ width: `${((s.n / total) * 100).toFixed(2)}%`, background: s.color }}
            title={`${s.model}: ${s.n}`}
          />
        ))}
      </div>
      <div className="legend">
        {segments.map((s) => (
          <span className="legend-item" key={s.model}>
            <i className="legend-swatch" style={{ background: s.color }} />
            <span className="nm">{s.model}</span>
            <span className="pc">
              {s.n} &middot; {((s.n / total) * 100).toFixed(0)}%
            </span>
          </span>
        ))}
      </div>
    </>
  );
}

export function RouteArena(p: Props) {
  const { boot, stats } = p;
  const activeMode = useMemo(
    () => boot.modes.modes.find((m) => m.key === p.mode) ?? boot.modes.modes[0],
    [boot.modes.modes, p.mode]
  );

  const modeOptions = boot.modes.modes.map((m) => ({
    value: m.key,
    label: m.label,
    title: `${m.description} (t = ${m.t.toFixed(2)})`,
  }));

  return (
    <Section
      id="arena"
      index="01"
      eyebrow="Route arena"
      title="Watch the router decide, live"
      lead="Type any prompt — or challenge the router. The trained scorer rates all eight
            models offline, estimates complexity, walks its cheapest-first cascade, and
            explains the decision."
    >
      <div className="arena">
        {/* ---------------------------------------------------- input column */}
        <Card variant="elevated" className="arena-input" as="div">
          <div>
            <span className="field-label">Routing policy</span>
            <Segmented
              ariaLabel="Routing policy"
              options={modeOptions}
              value={p.mode}
              onChange={p.onMode}
            />
            {activeMode ? (
              <p className="mode-note" style={{ marginTop: "var(--s3)" }}>
                <b>
                  {activeMode.label} (t = {activeMode.t.toFixed(2)})
                </b>{" "}
                — {activeMode.description}.{" "}
                {activeMode.val_accuracy_pct != null ? (
                  <>
                    Measured on the {activeMode.measured_on}:{" "}
                    {activeMode.val_accuracy_pct.toFixed(1)}% accuracy at{" "}
                    {fmtUSD(activeMode.val_avg_cost_per_query ?? 0, 4)}/query.{" "}
                  </>
                ) : null}
                {activeMode.meets_floor ? (
                  <Pill tone="ok">clears quality floor</Pill>
                ) : (
                  <Pill tone="warn">below quality floor</Pill>
                )}
                <br />
                Headline test-split numbers are for the Balanced policy.
              </p>
            ) : null}
          </div>

          <div>
            <label className="field-label" htmlFor="arena-query">
              Query
            </label>
            <textarea
              id="arena-query"
              className="textarea"
              rows={6}
              value={p.query}
              placeholder="Click a real benchmark query below, or type your own. Note: free-text prompts outside the benchmark format are routed conservatively."
              onChange={(e) => p.onQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) p.onRoute();
              }}
            />
          </div>

          <div className="arena-row">
            <div>
              <label className="field-label" htmlFor="arena-class">
                Capability class
              </label>
              <select
                id="arena-class"
                className="select"
                value={p.queryClass}
                onChange={(e) => p.onQueryClass(e.target.value)}
              >
                <option value="">auto-detect (heuristic)</option>
                {boot.models.classes.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <div className="threshold-row">
                <label className="field-label" htmlFor="arena-t" style={{ margin: 0 }}>
                  Confidence threshold
                </label>
                <span className="threshold-value">t = {p.threshold.toFixed(2)}</span>
              </div>
              <input
                id="arena-t"
                type="range"
                min={0.5}
                max={0.99}
                step={0.01}
                value={p.threshold}
                onChange={(e) => p.onThreshold(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="arena-actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={p.onRoute}
              disabled={p.busy || !p.query.trim()}
            >
              {p.busy ? "Routing…" : "Route it"}
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={p.onChallenge}
              disabled={p.busy || !boot.scenarios.challenges.length}
              title="Load a random real benchmark query"
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
                  title={`${s.query_class} — expected: ${
                    s.expected_route === "cheap" ? "cheap route" : "escalate to strongest"
                  }`}
                  onClick={() => {
                    p.onQuery(s.query);
                    p.onQueryClass(s.query_class);
                    p.onRouteWith(s.query, s.query_class);
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
            <p className="note" style={{ marginTop: "var(--s3)" }}>
              Source: {boot.scenarios.source}.
            </p>
          </div>

          <div className="arena-session">
            <div className="arena-session-head">
              <strong className="num">{stats?.session_queries ?? 0}</strong>
              <span className="note">queries routed this demo session</span>
              {stats && stats.session_queries > 0 ? (
                <Pill tone={stats.escalation_rate_pct > 50 ? "warn" : "ok"}>
                  {stats.escalation_rate_pct.toFixed(0)}% escalated
                </Pill>
              ) : null}
            </div>
            {stats ? <SessionBar boot={boot} stats={stats} /> : <Skeleton label="loading telemetry" />}
          </div>
        </Card>

        {/* -------------------------------------------------- decision column */}
        <Card variant="hero">
          {p.error ? (
            <EmptyState glyph="!" title="Routing failed" body={p.error} />
          ) : p.decision ? (
            <DecisionPanel decision={p.decision} models={boot.models.models} />
          ) : (
            <EmptyState
              glyph="◎"
              title="The routing decision appears here"
              body="Complexity estimate, per-model confidence, the cascade walk, the
                    reasoning, and what this query saves versus GPT-5."
            />
          )}
        </Card>
      </div>
    </Section>
  );
}
