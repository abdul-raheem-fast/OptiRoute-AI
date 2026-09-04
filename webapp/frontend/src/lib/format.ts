/** Shared number/text formatting so every surface reports figures identically. */

export function fmtUSD(value: number, digits = 0): string {
  const v = Number.isFinite(value) ? value : 0;
  return (
    "$" +
    v.toLocaleString("en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
  );
}

export function fmtPct(value: number, digits = 1): string {
  const v = Number.isFinite(value) ? value : 0;
  return `${v.toFixed(digits)}%`;
}

export function fmtInt(value: number): string {
  return Math.round(Number.isFinite(value) ? value : 0).toLocaleString("en-US");
}

/** Per-query costs are fractions of a cent — keep enough precision to compare. */
export function fmtQueryCost(value: number): string {
  const v = Number.isFinite(value) ? value : 0;
  return v < 0.001 ? `$${v.toFixed(6)}` : `$${v.toFixed(4)}`;
}

export function fmtLatency(seconds: number): string {
  const v = Number.isFinite(seconds) ? seconds : 0;
  return v < 1 ? `${(v * 1000).toFixed(0)} ms` : `${v.toFixed(2)} s`;
}

/** "Scientific Questionnaire" -> "Scientific Q." for tight table headers. */
export function shortClass(name: string): string {
  return name.replace("Questionnaire", "Q.").replace("Reasoning", "Reas.");
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
