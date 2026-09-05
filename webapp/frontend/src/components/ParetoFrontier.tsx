import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { CHART } from "../lib/palette";
import { fmtLatency, fmtUSD } from "../lib/format";
import type { MoFrontiers, ParetoPoint } from "../lib/types";

/**
 * Model-level Pareto frontier over MEASURED train-split statistics.
 *
 * This is NOT the policy frontier in FrontierChart.tsx (which plots routing
 * policies on the test split). Here every dot is one of the eight models, and
 * the encodings carry all four objectives at once:
 *
 *   x  = measured cost / query   (log scale - the pool spans ~4 orders)
 *   y  = measured accuracy       (train split)
 *   r  = measured latency        (bigger bubble = slower)
 *   ring = privacy-approved (locally hosted) model
 *
 * Frontier models are solid teal; dominated models are hollow slate and stay
 * on the canvas (a dominated model is never deleted - a privacy policy can
 * still make it the eligible choice elsewhere).
 */

interface DotPt extends ParetoPoint {
  acc: number;
  r: number;
  approved: boolean;
}

const LOCAL_GREEN = "#34d399";

function latencyRadius(latency_s: number, lo: number, hi: number): number {
  const span = hi - lo || 1;
  const t = Math.min(1, Math.max(0, (latency_s - lo) / span));
  return 6 + t * 12; // 6px (fastest) -> 18px (slowest)
}

/** Specific label placement offsets based on bubble size to prevent overlaps */
const LABEL_CONFIG: Record<string, { anchor: "start" | "end" | "middle"; getOffset: (r: number) => { dx: number; dy: number } }> = {
  "Llama-3.1-8B-Instruct": { anchor: "start", getOffset: (r) => ({ dx: r + 7, dy: 4 }) },
  "Qwen3-8B": { anchor: "middle", getOffset: (r) => ({ dx: 0, dy: -(r + 8) }) },
  "deepseek-v3-0324": { anchor: "middle", getOffset: (r) => ({ dx: 0, dy: r + 16 }) },
  "gemini-2.5-flash": { anchor: "end", getOffset: (r) => ({ dx: -(r + 7), dy: -6 }) },
  "gpt-4.1": { anchor: "start", getOffset: (r) => ({ dx: r + 7, dy: 14 }) },
  "claude-sonnet-4": { anchor: "middle", getOffset: (r) => ({ dx: 0, dy: -(r + 8) }) },
  "gpt-5": { anchor: "end", getOffset: (r) => ({ dx: -(r + 8), dy: -4 }) },
  "gemini-2.5-pro": { anchor: "end", getOffset: (r) => ({ dx: -(r + 8), dy: 4 }) },
};

function Dot(props: Record<string, unknown>) {
  const cx = Number(props.cx ?? 0);
  const cy = Number(props.cy ?? 0);
  const p = props.payload as DotPt | undefined;
  if (!p) return <g />;
  const frontier = p.on_global_frontier;
  const fill = frontier ? CHART.accent : CHART.baseline;
  const cfg = LABEL_CONFIG[p.model];
  const pos = cfg
    ? { anchor: cfg.anchor, ...cfg.getOffset(p.r) }
    : { anchor: "middle" as const, dx: 0, dy: -(p.r + 6) };

  return (
    <g>
      {frontier ? <circle cx={cx} cy={cy} r={p.r + 6} fill={fill} opacity={0.14} /> : null}
      <circle
        cx={cx}
        cy={cy}
        r={p.r}
        fill={fill}
        fillOpacity={frontier ? 0.9 : 0.38}
        stroke={p.approved ? LOCAL_GREEN : "var(--surface)"}
        strokeWidth={p.approved ? 3 : 2}
        style={frontier ? { filter: `drop-shadow(0 0 7px ${fill})` } : undefined}
      />
      <text
        x={cx + pos.dx}
        y={cy + pos.dy}
        textAnchor={pos.anchor}
        fill={frontier ? "var(--text)" : "var(--text-2)"}
        fontSize={11}
        fontWeight={frontier ? 700 : 500}
        fontFamily="var(--font-mono)"
      >
        {p.model}
      </text>
    </g>
  );
}

function ParetoTooltip({ active, payload }: { active?: boolean; payload?: { payload: DotPt }[] }) {
  const p = active && payload?.length ? payload[0]?.payload : undefined;
  if (!p) return null;
  return (
    <div className="rc-tooltip">
      <div className="t-title">{p.model}</div>
      <div className="t-row">{p.acc.toFixed(2)}% accuracy &middot; {fmtUSD(p.cost, 6)}/query</div>
      <div className="t-row">{fmtLatency(p.latency_s)} measured latency</div>
      <div className="t-row">
        {p.on_global_frontier ? "on the global Pareto frontier" : `dominated by ${p.dominated_by.join(", ") || "-"}`}
      </div>
      {p.approved ? <div className="t-row">privacy-approved (locally hosted)</div> : null}
    </div>
  );
}

interface Props {
  points: ParetoPoint[];
  frontiers: MoFrontiers;
  approved: string[];
}

export function ParetoFrontier({ points, frontiers, approved }: Props) {
  if (!points.length) return <p className="legend-empty">No model points available.</p>;

  const latencies = points.map((p) => p.latency_s);
  const lo = Math.min(...latencies);
  const hi = Math.max(...latencies);
  const approvedSet = new Set(approved);

  const dots: DotPt[] = points.map((p) => {
    const rawAcc = p.quality <= 1 ? p.quality * 100 : p.quality;
    return {
      ...p,
      acc: Number(rawAcc.toFixed(2)),
      r: latencyRadius(p.latency_s, lo, hi),
      approved: approvedSet.has(p.model),
    };
  });

  const costs = points.map((p) => p.cost).filter((c) => c > 0);
  const minCost = Math.min(...costs) * 0.6;
  const maxCost = Math.max(...costs) * 1.8;

  const accs = dots.map((d) => d.acc);
  const minQ = Math.max(0, Math.floor(Math.min(...accs) - 6));
  const maxQ = Math.min(100, Math.ceil(Math.max(...accs) + 6));

  // Split so dominated dots render first (behind the frontier).
  const dominated = dots.filter((d) => !d.on_global_frontier);
  const frontier = dots.filter((d) => d.on_global_frontier);

  return (
    <div>
      <div className="chart-box" style={{ height: 440 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 24, right: 48, bottom: 36, left: 16 }}>
            <CartesianGrid stroke={CHART.grid} strokeDasharray="3 5" />
            <XAxis
              type="number"
              dataKey="cost"
              name="cost"
              scale="log"
              domain={[minCost, maxCost]}
              allowDataOverflow
              tickFormatter={(v: number) => `$${v.toExponential(0)}`}
              tick={{ fill: CHART.axis, fontSize: 11, fontFamily: "var(--font-mono)" }}
              stroke={CHART.grid}
              label={{
                value: "measured cost / query (USD, log scale)",
                position: "insideBottom",
                offset: -22,
                fill: CHART.axis,
                fontSize: 11.5,
                letterSpacing: "0.05em",
              }}
            />
            <YAxis
              type="number"
              dataKey="acc"
              name="accuracy"
              unit="%"
              domain={[minQ, maxQ]}
              allowDataOverflow
              tickCount={5}
              tickFormatter={(v: number) => `${Math.round(v)}%`}
              tick={{ fill: CHART.axis, fontSize: 11, fontFamily: "var(--font-mono)" }}
              stroke={CHART.grid}
              width={62}
              label={{
                value: "measured accuracy",
                angle: -90,
                position: "insideLeft",
                fill: CHART.axis,
                fontSize: 11.5,
                letterSpacing: "0.05em",
                style: { textAnchor: "middle" },
              }}
            />
            <ZAxis type="number" dataKey="r" range={[64, 324]} />
            <Tooltip
              cursor={{ strokeDasharray: "4 4", stroke: CHART.cursor }}
              content={<ParetoTooltip />}
            />
            <Scatter data={dominated} shape={<Dot />} isAnimationActive={false} />
            <Scatter data={frontier} shape={<Dot />} isAnimationActive={false} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="pareto-legend">
        <span className="legend-item">
          <i className="legend-swatch" style={{ background: CHART.accent, borderRadius: "50%" }} />
          <span className="nm">on frontier</span>
        </span>
        <span className="legend-item">
          <i className="legend-swatch" style={{ background: CHART.baseline, opacity: 0.4, borderRadius: "50%" }} />
          <span className="nm">dominated</span>
        </span>
        <span className="legend-item">
          <i className="legend-swatch" style={{ border: `3px solid ${LOCAL_GREEN}`, borderRadius: "50%", background: "transparent" }} />
          <span className="nm">privacy-approved (local)</span>
        </span>
        <span className="legend-item">
          <span className="nm dim">bubble size = measured latency (bigger = slower)</span>
        </span>
      </div>

      <p className="chart-caption">
        Global frontier: <b>{frontiers.global.join(", ") || "none"}</b>. Under the configured
        quality floor only <b>{frontiers.quality_floor.join(", ") || "none"}</b> stays admissible,
        and the privacy-approved frontier is <b>{frontiers.privacy_approved.join(", ") || "none"}</b>.
        Dominated models are kept in the pool, not deleted — a different privacy policy can make
        one of them the eligible choice.
      </p>
    </div>
  );
}
