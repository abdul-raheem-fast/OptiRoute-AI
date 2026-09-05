import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardTitle, Section, StatTile } from "./ui";
import { fmtInt, fmtUSD } from "../lib/format";
import { CHART, modelColor, TIER_COLORS } from "../lib/palette";
import type { Bootstrap, StatsPayload } from "../lib/types";

const TIERS = ["easy", "medium", "hard"];

function DistBar({
  segments,
  ariaLabel,
}: {
  segments: { key: string; label: string; n: number; color: string }[];
  ariaLabel: string;
}) {
  const total = segments.reduce((a, s) => a + s.n, 0);
  if (!total) {
    return <p className="legend-empty">No data yet — route a query in the arena.</p>;
  }
  return (
    <>
      <div className="distbar" role="img" aria-label={ariaLabel}>
        {segments
          .filter((s) => s.n > 0)
          .map((s) => (
            <span
              key={s.key}
              style={{ width: `${((s.n / total) * 100).toFixed(2)}%`, background: s.color }}
              title={`${s.label}: ${s.n}`}
            />
          ))}
      </div>
      <div className="legend">
        {segments.map((s) => (
          <span className="legend-item" key={s.key}>
            <i className="legend-swatch" style={{ background: s.color }} />
            <span className="nm">{s.label}</span>
            <span className="pc">
              {s.n} &middot; {((s.n / total) * 100).toFixed(0)}%
            </span>
          </span>
        ))}
      </div>
    </>
  );
}

function SavingsTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: { i: number; saved: number } }[];
}) {
  const p = active && payload?.length ? payload[0]?.payload : undefined;
  if (!p) return null;
  return (
    <div className="rc-tooltip">
      <div className="t-title">route #{p.i + 1}</div>
      <div className="t-row">cumulative saved {fmtUSD(p.saved, 4)}</div>
    </div>
  );
}

export function Operations({ boot, stats }: { boot: Bootstrap; stats: StatsPayload | null }) {
  const s = stats;
  const modelSegments = boot.models.models.map((m, i) => ({
    key: m.model,
    label: m.model,
    n: s?.distribution[m.model] ?? 0,
    color: modelColor(i),
  }));
  const tierSegments = TIERS.map((t) => ({
    key: t,
    label: t,
    n: s?.tier_distribution[t] ?? 0,
    color: TIER_COLORS[t],
  }));

  const curve = (() => {
    let cum = 0;
    return (s?.route_log ?? []).map((r, i) => {
      cum += r.saved;
      return { i, saved: Number(cum.toFixed(6)) };
    });
  })();

  return (
    <Section
      id="operations"
      index="08"
      eyebrow="Operations"
      title="Live telemetry of this demo session"
      lead="In-memory counters for this demo session — every query routed, not production traffic. Ephemeral: they reset when the server instance restarts."
    >
      <div className="ops-tiles">
        <StatTile accent value={fmtInt(s?.session_queries ?? 0)} label="Queries routed" />
        <StatTile value={fmtInt(s?.efficient_routes ?? 0)} label="Efficient routes" />
        <StatTile value={fmtInt(s?.escalations ?? 0)} label="Escalations to strongest" />
        <StatTile value={(s?.escalation_rate_pct ?? 0).toFixed(1)} unit="%" label="Escalation rate" />
        <StatTile value={fmtUSD(s?.est_savings_total ?? 0, 2)} label="Est. session savings" />
      </div>

      <div className="ops-charts">
        <Card variant="elevated">
          <CardTitle hint="cheapest → strongest">Routing distribution by model</CardTitle>
          <DistBar segments={modelSegments} ariaLabel="Routing distribution by model" />
        </Card>

        <Card variant="elevated">
          <CardTitle hint="router-derived">Complexity mix</CardTitle>
          <DistBar segments={tierSegments} ariaLabel="Complexity tier mix" />
        </Card>

        <Card variant="elevated" className="span-2">
          <CardTitle hint={`${curve.length} routes logged`}>
            Cumulative estimated savings
          </CardTitle>
          {curve.length > 1 ? (
            <div className="chart-box" style={{ height: 220 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={curve} margin={{ top: 12, right: 18, bottom: 6, left: 6 }}>
                  <defs>
                    <linearGradient id="savingsFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART.accent} stopOpacity={0.42} />
                      <stop offset="100%" stopColor={CHART.accent} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={CHART.grid} strokeDasharray="3 5" vertical={false} />
                  <XAxis
                    dataKey="i"
                    tickFormatter={(v: number) => `#${v + 1}`}
                    tick={{ fill: CHART.axis, fontSize: 11, fontFamily: "var(--font-mono)" }}
                    stroke={CHART.grid}
                  />
                  <YAxis
                    tickFormatter={(v: number) => fmtUSD(v, 2)}
                    tick={{ fill: CHART.axis, fontSize: 11, fontFamily: "var(--font-mono)" }}
                    stroke={CHART.grid}
                    width={66}
                  />
                  <Tooltip content={<SavingsTooltip />} cursor={{ stroke: CHART.cursor }} />
                  <Area
                    type="monotone"
                    dataKey="saved"
                    stroke={CHART.accent}
                    strokeWidth={2.25}
                    fill="url(#savingsFill)"
                    dot={false}
                    activeDot={{ r: 4.5, fill: CHART.accent, stroke: "var(--surface)", strokeWidth: 2 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="legend-empty">
              Route queries in the arena to draw the cumulative savings curve.
            </p>
          )}
          <p className="chart-caption">
            Savings are per-query estimates: the benchmark average cost of the strongest
            model minus the benchmark average cost of the routed model.
          </p>
        </Card>
      </div>
    </Section>
  );
}
