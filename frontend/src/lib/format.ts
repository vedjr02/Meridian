// Formatting is fixed to en-US so server and client render identical text (no hydration mismatch)
// and every figure reads the same as in the written summary.

const integer = new Intl.NumberFormat("en-US");

/** Whole-number counts with thousands separators: 31,509. */
export function formatCount(value: number): string {
  return integer.format(value);
}

/** Shares as percentages with one decimal: 7.0%. */
export function formatShare(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/** Durations given in seconds, as days with one decimal, or hours below one day. */
export function formatDurationSeconds(seconds: number): string {
  if (seconds < 86_400) return `${(seconds / 3_600).toFixed(1)} h`;
  return `${(seconds / 86_400).toFixed(1)} d`;
}

/** Short durations for edge timing, where minutes and seconds matter: 24 s, 3.2 min, 20.7 h. */
export function formatShortDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3_600) return `${(seconds / 60).toFixed(1)} min`;
  return formatDurationSeconds(seconds);
}

/** Heuristic-miner measures are strictly below 1, so never print a certain-looking 1.000. */
export function formatMeasure(value: number): string {
  return value >= 0.9995 ? ">0.999" : value.toFixed(3);
}
