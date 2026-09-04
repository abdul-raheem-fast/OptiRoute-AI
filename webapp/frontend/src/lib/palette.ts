/**
 * Chart and segment colours.
 *
 * These are literal hex values rather than CSS custom properties so Recharts
 * can consume them directly in SVG props. They mirror the accent ramp defined
 * in styles.css and stay legible on both the dark and light surfaces.
 */

/** Cheapest -> strongest, matching the cascade order in models_registry.json. */
export const MODEL_COLORS = [
  "#2dd4bf", // teal   (self-hosted / cheapest)
  "#38bdf8", // sky
  "#818cf8", // indigo
  "#a78bfa", // violet
  "#f472b6", // pink
  "#fb923c", // orange
  "#fbbf24", // amber
  "#fb7185", // rose   (strongest)
];

export const TIER_COLORS: Record<string, string> = {
  easy: "#34d399",
  medium: "#fbbf24",
  hard: "#fb7185",
};

export const CHART = {
  accent: "#2dd4bf",
  accentAlt: "#38bdf8",
  learned: "#2dd4bf",
  oracle: "#a78bfa",
  baseline: "#64748b",
  floor: "#fb7185",
  grid: "rgba(148, 163, 184, 0.16)",
  axis: "#8b97a8",
  cursor: "rgba(148, 163, 184, 0.10)",
};

export function modelColor(index: number): string {
  return MODEL_COLORS[index % MODEL_COLORS.length];
}
