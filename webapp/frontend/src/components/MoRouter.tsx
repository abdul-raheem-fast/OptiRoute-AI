import { useCallback, useEffect, useRef, useState } from "react";
import { Card, EmptyState, Pill, Section, Segmented, Skeleton } from "./ui";
import { MoDecision } from "./MoDecision";
import { routeMo } from "../lib/api";
import { fmtLatency, fmtUSD } from "../lib/format";
import { modelColor } from "../lib/palette";
import type { Bootstrap, MoMode, MoRouteDecision } from "../lib/types";
import type { MultiObjective } from "../lib/api";

type SensMode = "auto" | "normal" | "sensitive";

/** Fixed cheap -> strong order, matching routing/config.py MODELS. */
const MODEL_ORDER = [
  "Llama-3.1-8B-Instruct", "Qwen3-8B", "deepseek-v3-0324", "gemini-2.5-flash",
  "gpt-4.1", "claude-sonnet-4", "gemini-2.5-pro", "gpt-5",
];

interface Props {
  boot: Bootstrap;
  mo: MultiObjective;
  loading: boolean;
}

/** The multi-objective playground: pick an objective, set the hard constraints,
 *  and watch the router choose the best ELIGIBLE model - with the measured
 *  validation evidence for that objective shown beside the controls. */
export function MoRouter({ boot, mo, loading }: Props) {
  const [mode, setMode] = useState<MoMode>("balanced");
  const [query, setQuery] = useState("");
  const [queryClass, setQueryClass] = useState("");
  const [budgetOn, setBudgetOn] = useState(false);
  const [budgetMs, setBudgetMs] = useState(1000);
  const [floorOn, setFloorOn] = useState(false);
  const [floor, setFloor] = useState(0.8);
  const [sens, setSens] = useState<SensMode>("auto");
  const [decision, setDecision] = useState<MoRouteDecision | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const spec = mo.objectives?.modes[mode];

  const run = useCallback(
    async (q: string, cls: string, m: MoMode, bOn: boolean, bMs: number, fOn: boolean, f: number, s: SensMode) => {
      const text = q.trim();
      if (!text) return;
      setBusy(true);
      setError(null);
      try {
        const d = await routeMo({
          query: text,
          query_class: cls || null,
          mode: m,
          latency_budget_ms: bOn ? bMs : null,
          quality_floor: fOn ? f : null,
          sensitive: s === "auto" ? null : s === "sensitive",
        });
        setDecision(d);
      } catch (e) {
        setDecision(null);
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    []
  );

  // Open with a real benchmark query already routed through the default objective.
  const autoRan = useRef(false);
  useEffect(() => {
    if (!mo.available || autoRan.current) return;
    const first = boot.scenarios.scenarios[0];
    if (!first) return;
    autoRan.current = true;
    setQuery(first.query);
    setQueryClass(first.query_class);
    void run(first.query, first.query_class, mode, budgetOn, budgetMs, floorOn, floor, sens);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mo.available]);

  const rerun = (patch: Partial<{ mode: MoMode; budgetOn: boolean; budgetMs: number; floorOn: boolean; floor: number; sens: SensMode }> = {}) => {
    const next = { mode, budgetOn, budgetMs, floorOn, floor, sens, ...patch };
    if (query.trim()) void run(query, queryClass, next.mode, next.budgetOn, next.budgetMs, next.floorOn, next.floor, next.sens);
  };

  const modeOptions = (mo.objectives?.mode_order ?? []).map((k) => ({
    value: k,
    label: mo.objectives!.modes[k].label,
    title: mo.objectives!.modes[k].description,
  }));

  if (loading) return <Section id="mo" index="02" eyebrow="Multi-objective" title="Multi-objective router"><Skeleton label="loading multi-objective router" /></Section>;

  if (!mo.available || !mo.objectives) {
    return (
      <Section
        id="mo"
        index="02"
        eyebrow="Multi-objective"
        title="Multi-objective router (experimental)"
        lead="Balances quality, cost, latency and privacy under a configurable objective."
      >
        <Card variant="elevated">
          <EmptyState
            glyph="◎"
            title="Multi-objective artifact not built"
            body={<>Run <code className="mono">python -m routing.tune_mo</code> to fit the calibration + objective artifact, then reload. The legacy router above is unaffected.</>}
          />
        </Card>
      </Section>
    );
  }

  const mix = spec?.val_model_mix ?? {};
  const mixTop = Object.entries(mix).filter(([, n]) => (n as number) > 0).sort((a, b) => (b[1] as number) - (a[1] as number));
  const mixTotal = mixTop.reduce((s, [, n]) => s + (n as number), 0) || 1;

  return (
    <Section
      id="mo"
      index="02"
      eyebrow="Multi-objective"
      title="Multi-objective router"
      lead="The same frozen heads, now selecting under an explicit objective: calibrated quality
            minus weighted cost and latency, behind hard privacy and latency constraints. This is
            an experimental view — the legacy cascade above remains the production default."
    >
      <div className="arena">
        {/* ------------------------------------------------------ controls */}
        <Card variant="elevated" className="arena-input" as="div">
          <div>
            <span className="field-label">Routing objective</span>
            <Segmented
              ariaLabel="Routing objective"
              options={modeOptions}
              value={mode}
              onChange={(k) => {
                setMode(k);
                rerun({ mode: k });
              }}
            />
            {spec ? (
              <div className="mo-spec">
                <p className="mode-note">{spec.description}</p>
                <div className="constraint-chips">
                  <span className="cchip">λ<sub>cost</sub> = {spec.lambda_cost}</span>
                  <span className="cchip">λ<sub>latency</sub> = {spec.lambda_latency}</span>
                  <span className="cchip">{spec.privacy_restricted ? "privacy-restricted" : "full pool eligible"}</span>
                  {spec.latency_budget_ms != null ? <span className="cchip is-on">budget {spec.latency_budget_ms.toFixed(0)} ms</span> : null}
                </div>
                <div className="mo-val">
                  <span className="mv"><i>val accuracy</i><b className="num">{spec.val.accuracy_pct.toFixed(2)}%</b></span>
                  <span className="mv"><i>val cost/q</i><b className="num">{fmtUSD(spec.val.avg_cost_per_query, 6)}</b></span>
                  <span className="mv"><i>val latency</i><b className="num">{fmtLatency(spec.val.avg_latency_s)}</b></span>
                  <span className="mv"><i>val p95</i><b className="num">{fmtLatency(spec.val.p95_latency_s)}</b></span>
                  <span className="mv">
                    <i>quality floor</i>
                    {spec.val_meets_floor == null ? (
                      <Pill tone="info">n/a</Pill>
                    ) : spec.val_meets_floor ? (
                      <Pill tone="ok">meets</Pill>
                    ) : (
                      <Pill tone="warn">below</Pill>
                    )}
                  </span>
                </div>
                {mixTop.length ? (
                  <div className="mo-mix">
                    <span className="field-label">val model mix</span>
                    <div className="distbar" role="img" aria-label="Validation model mix for this objective">
                      {mixTop.map(([m, n]) => (
                        <span
                          key={m}
                          style={{
                            width: `${(((n as number) / mixTotal) * 100).toFixed(1)}%`,
                            background: modelColor(MODEL_ORDER.indexOf(m)),
                          }}
                          title={`${m}: ${n}`}
                        />
                      ))}
                    </div>
                    <div className="legend">
                      {mixTop.map(([m, n]) => (
                        <span className="legend-item" key={m}>
                          <span className="nm mono">{m}</span>
                          <span className="pc">{(((n as number) / mixTotal) * 100).toFixed(0)}%</span>
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>

          <div>
            <label className="field-label" htmlFor="mo-query">Query</label>
            <textarea
              id="mo-query"
              className="textarea"
              rows={4}
              value={query}
              placeholder="Click a real benchmark query below, or type your own."
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) rerun();
              }}
            />
          </div>

          <div className="arena-row">
            <div>
              <label className="field-label" htmlFor="mo-class">Capability class</label>
              <select id="mo-class" className="select" value={queryClass} onChange={(e) => setQueryClass(e.target.value)}>
                <option value="">auto-detect (heuristic)</option>
                {boot.models.classes.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div>
              <span className="field-label">Query sensitivity</span>
              <Segmented
                ariaLabel="Query sensitivity"
                options={[
                  { value: "auto", label: "Auto (local classifier)" },
                  { value: "normal", label: "Normal" },
                  { value: "sensitive", label: "Sensitive" },
                ]}
                value={sens}
                onChange={(s) => {
                  setSens(s);
                  rerun({ sens: s });
                }}
              />
            </div>
          </div>

          {/* ---- hard constraints (both optional; off = mode's own policy) ---- */}
          <div className="mo-constraints">
            <label className="mo-toggle">
              <input type="checkbox" checked={budgetOn} onChange={(e) => { setBudgetOn(e.target.checked); rerun({ budgetOn: e.target.checked }); }} />
              <span>Latency budget (hard filter)</span>
            </label>
            <div className="mo-slider">
              <input
                type="range" min={100} max={4000} step={20} value={budgetMs} disabled={!budgetOn}
                onChange={(e) => { setBudgetMs(Number(e.target.value)); }}
                onMouseUp={() => rerun({ budgetMs })}
                onTouchEnd={() => rerun({ budgetMs })}
              />
              <span className="threshold-value num">{budgetMs} ms</span>
            </div>

            <label className="mo-toggle">
              <input type="checkbox" checked={floorOn} onChange={(e) => { setFloorOn(e.target.checked); rerun({ floorOn: e.target.checked }); }} />
              <span>Per-query quality floor (hard gate)</span>
            </label>
            <div className="mo-slider">
              <input
                type="range" min={0.5} max={0.99} step={0.01} value={floor} disabled={!floorOn}
                onChange={(e) => { setFloor(Number(e.target.value)); }}
                onMouseUp={() => rerun({ floor })}
                onTouchEnd={() => rerun({ floor })}
              />
              <span className="threshold-value num">{floor.toFixed(2)}</span>
            </div>
            <p className="note">
              Off by default: each objective already carries a policy-level quality target verified
              on the validation split. Enabling these adds a HARD per-query constraint on top.
            </p>
          </div>

          <div className="arena-actions">
            <button type="button" className="btn btn--primary" onClick={() => rerun()} disabled={busy || !query.trim()}>
              {busy ? "Routing…" : "Route it"}
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
                  title={`${s.query_class} — expected: ${s.expected_route === "cheap" ? "cheap route" : "escalate"}`}
                  onClick={() => {
                    setQuery(s.query);
                    setQueryClass(s.query_class);
                    void run(s.query, s.query_class, mode, budgetOn, budgetMs, floorOn, floor, sens);
                  }}
                >
                  {s.label}
                </button>
              ))}
            </div>
            <p className="note" style={{ marginTop: "var(--s3)" }}>Source: {boot.scenarios.source}.</p>
          </div>
        </Card>

        {/* ------------------------------------------------------ decision */}
        <Card variant="hero">
          {error ? (
            <EmptyState glyph="!" title="Routing failed" body={error} />
          ) : decision ? (
            <MoDecision d={decision} />
          ) : (
            <EmptyState
              glyph="◎"
              title="The multi-objective decision appears here"
              body="Selected model, calibrated routing score, estimated cost, the three-part latency
                    breakdown, privacy status, the explanation, and the eligible-frontier comparison."
            />
          )}
        </Card>
      </div>
    </Section>
  );
}
