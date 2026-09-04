import {
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART } from "../lib/palette";
import { fmtUSD } from "../lib/format";
import type { PolicyRow } from "../lib/types";

interface Pt {
  name: string;
  cost: number;
  acc: number;
  kind: "learned" | "oracle" | "base";
  quality: number;
  cut: number;
  floor: boolean;
}

/** Per-policy label placement so the eight labels never collide. */
const LABEL_POS: Record<string, { anchor: "start" | "end" | "middle"; dx: number; dy: number }> = {
  "always-strongest": { anchor: "end", dx: -12, dy: 16 },
  "knn-cascade": { anchor: "end", dx: -12, dy: -12 },
  "learned-cascade": { anchor: "end", dx: -12, dy: -16 },
  "prior-cascade": { anchor: "end", dx: -12, dy: -12 },
  "class-based": { anchor: "end", dx: -12, dy: 15 },
  oracle: { anchor: "start", dx: 12, dy: 4 },
  random: { anchor: "end", dx: -12, dy: 4 },
  "always-cheapest": { anchor: "start", dx: 12, dy: 4 },
};

const COLOR: Record<Pt["kind"], string> = {
  learned: CHART.learned,
  oracle: CHART.oracle,
  base: CHART.baseline,
};
const RADIUS: Record<Pt["kind"], number> = { learned: 8, oracle: 8, base: 5.5 };

function buildPoints(rows: PolicyRow[]): Pt[] {
  return rows.map((r) => ({
    name: r.policy.replace(/ \(t=.*\)/, ""),
    cost: Number(r.avg_cost_per_query),
    acc: Number(r.accuracy_pct),
    kind: r.policy.startsWith("learned") ? "learned" : r.policy === "oracle" ? "oracle" : "base",
    quality: Number(r.quality_vs_strongest_pct),
    cut: Number(r.cost_reduction_vs_strongest_pct),
    floor: r.meets_quality_floor === true || String(r.meets_quality_floor) === "True",
  }));
}

/**
 * Dot + its policy label, drawn together.
 *
 * Recharts passes `payload` to a custom `shape` but NOT to `LabelList` content,
 * so the label is rendered here rather than through a separate LabelList.
 */
function Dot(props: Record<string, unknown>) {
  const cx = Number(props.cx ?? 0);
  const cy = Number(props.cy ?? 0);
  const payload = props.payload as Pt | undefined;
  if (!payload) return <g />;

  const r = RADIUS[payload.kind];
  const fill = COLOR[payload.kind];
  const pos = LABEL_POS[payload.name] ?? { anchor: "start", dx: 12, dy: 4 };

  return (
    <g>
      {payload.kind !== "base" ? (
        <circle cx={cx} cy={cy} r={r + 7} fill={fill} opacity={0.16} />
      ) : null}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill={fill}
        stroke="var(--surface)"
        strokeWidth={2}
        style={{ filter: payload.kind === "learned" ? `drop-shadow(0 0 8px ${fill})` : undefined }}
      />
      <text
        x={cx + pos.dx}
        y={cy + pos.dy}
        textAnchor={pos.anchor}
        fill={payload.kind === "base" ? "var(--text-3)" : fill}
        fontSize={11.5}
        fontWeight={payload.kind === "base" ? 500 : 700}
        fontFamily="var(--font-mono)"
      >
        {payload.name}
      </text>
    </g>
  );
}

function FrontierTooltip({ active, payload }: { active?: boolean; payload?: { payload: Pt }[] }) {
  const p = active && payload?.length ? payload[0]?.payload : undefined;
  if (!p) return null;
  return (
    <div className="rc-tooltip">
      <div className="t-title">{p.name}</div>
      <div className="t-row">{p.acc.toFixed(2)}% accuracy &middot; {p.quality.toFixed(1)}% of flagship</div>
      <div className="t-row">{fmtUSD(p.cost, 6)} / query &middot; {p.cut.toFixed(1)}% cheaper</div>
      <div className="t-row">{p.floor ? "clears quality floor" : "below quality floor"}</div>
    </div>
  );
}

export function FrontierChart({ rows }: { rows: PolicyRow[] }) {
  const pts = buildPoints(rows);
  if (!pts.length) return <p className="legend-empty">No policy rows available.</p>;

  const strongest = rows.find((r) => r.policy === "always-strongest");
  const floorAcc = strongest ? Number(strongest.accuracy_pct) * 0.9 : 0;
  const maxCost = Math.max(...pts.map((p) => p.cost)) * 1.18;
  const minAcc = Math.min(...pts.map((p) => p.acc)) - 5;
  const maxAcc = Math.max(...pts.map((p) => p.acc)) + 4;

  return (
    <div className="chart-box" style={{ height: 400 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 18, right: 26, bottom: 26, left: 8 }}>
          <CartesianGrid stroke={CHART.grid} strokeDasharray="3 5" />
          <XAxis
            type="number"
            dataKey="cost"
            name="cost"
            domain={[0, maxCost]}
            tickCount={5}
            tickFormatter={(v: number) => `$${v.toFixed(3)}`}
            tick={{ fill: CHART.axis, fontSize: 11.5, fontFamily: "var(--font-mono)" }}
            stroke={CHART.grid}
            label={{
              value: "avg cost per query (USD)",
              position: "insideBottom",
              offset: -18,
              fill: CHART.axis,
              fontSize: 11.5,
              letterSpacing: "0.06em",
            }}
          />
          <YAxis
            type="number"
            dataKey="acc"
            name="accuracy"
            unit="%"
            domain={[minAcc, maxAcc]}
            tick={{ fill: CHART.axis, fontSize: 11.5, fontFamily: "var(--font-mono)" }}
            stroke={CHART.grid}
            width={52}
            label={{
              value: "accuracy (test split)",
              angle: -90,
              position: "insideLeft",
              fill: CHART.axis,
              fontSize: 11.5,
              letterSpacing: "0.06em",
              style: { textAnchor: "middle" },
            }}
          />
          <ReferenceArea
            y1={minAcc}
            y2={floorAcc}
            fill={CHART.floor}
            fillOpacity={0.07}
            stroke="none"
          />
          <ReferenceLine
            y={floorAcc}
            stroke={CHART.floor}
            strokeDasharray="5 4"
            strokeOpacity={0.7}
            label={{
              value: `quality floor ${floorAcc.toFixed(1)}%`,
              position: "insideTopRight",
              fill: CHART.floor,
              fontSize: 11,
              fontFamily: "var(--font-mono)",
            }}
          />
          <Tooltip
            cursor={{ strokeDasharray: "4 4", stroke: CHART.cursor }}
            content={<FrontierTooltip />}
          />
          <Scatter data={pts} shape={<Dot />} isAnimationActive={false} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
