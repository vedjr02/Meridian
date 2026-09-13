import { formatCount, formatDurationSeconds } from "@/lib/format";
import type { DistributionSeconds, Histogram, Overview } from "@/lib/discovery";

import styles from "./discovery.module.css";

const WIDTH = 900;
const HEIGHT = 250;
const MARGIN = { top: 34, right: 16, bottom: 34, left: 52 };
const OVERFLOW_GAP_BINS = 1;

type CycleTimeHistogramProps = {
  histogram: Histogram;
  overview: Overview;
};

/**
 * Cycle time as a distribution, never a single number (03-UIUX-RULES.md rule 1). Bars show case
 * counts per bin, split into the most common variant and all others; dashed lines mark p50, p90
 * and p99; cases beyond the last bin are drawn as a separate, hatched overflow bar so the long
 * tail is visible without flattening the rest of the chart. A table repeats the percentiles per
 * group for exact reading.
 */
export default function CycleTimeHistogram({ histogram, overview }: CycleTimeHistogramProps) {
  const { bins, overflow, percentiles, bin_width: binWidth } = histogram;
  const slots = bins.length + OVERFLOW_GAP_BINS + 1;
  const plotWidth = WIDTH - MARGIN.left - MARGIN.right;
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
  const slotWidth = plotWidth / slots;
  const maxCount = Math.max(1, overflow.all_cases, ...bins.map((bin) => bin.all_cases));
  const y = (count: number) => MARGIN.top + plotHeight - (count / maxCount) * plotHeight;
  const xForDays = (days: number) => MARGIN.left + (days / binWidth) * slotWidth;
  const tickEvery = Math.max(1, Math.round(10 / binWidth));

  const markers = [
    { label: "p50", days: percentiles.p50 },
    { label: "p90", days: percentiles.p90 },
    { label: "p99", days: percentiles.p99 },
  ];
  const overflowX = MARGIN.left + (bins.length + OVERFLOW_GAP_BINS) * slotWidth;
  const cycle = overview.cycle_time_seconds;
  const rows: [string, DistributionSeconds | null][] = [
    ["All cases", cycle.all_cases],
    ["Most common variant", cycle.most_common_variant],
    ["All other variants", cycle.other_variants],
  ];

  return (
    <div>
      <div className={styles.panelHeader}>
        <h2 id="cycle-title">Cycle time distribution</h2>
        <p>
          First to last event per case, {formatCount(histogram.case_count)} cases, bins of{" "}
          {binWidth} {binWidth === 1 ? "day" : "days"}
        </p>
      </div>
      <ul className={styles.legend} aria-label="Histogram series">
        <li><span className={`${styles.swatch} ${styles.barOtherSwatch}`} aria-hidden="true" />other variants</li>
        <li><span className={`${styles.swatch} ${styles.barTopSwatch}`} aria-hidden="true" />most common variant</li>
        <li><span className={`${styles.legendLine} ${styles.legendMarker}`} aria-hidden="true" />percentile</li>
      </ul>
      <svg className={styles.histogram} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`Histogram of cycle times: p50 ${percentiles.p50.toFixed(1)} days, p90 ${percentiles.p90.toFixed(1)} days, p99 ${percentiles.p99.toFixed(1)} days; ${formatCount(overflow.all_cases)} cases take ${overflow.start} days or longer.`}>
        <defs>
          <pattern id="overflow-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" className={styles.hatchBackground} />
            <line x1="0" y1="0" x2="0" y2="6" className={styles.hatchLine} />
          </pattern>
        </defs>

        <line x1={MARGIN.left} x2={WIDTH - MARGIN.right} y1={y(0)} y2={y(0)} className={styles.axis} />
        <text x={MARGIN.left - 8} y={y(maxCount) + 4} className={styles.axisLabel} textAnchor="end">
          {formatCount(maxCount)}
        </text>
        <text x={MARGIN.left - 8} y={y(0) + 4} className={styles.axisLabel} textAnchor="end">
          0
        </text>

        {bins.map((bin, index) => {
          const x = MARGIN.left + index * slotWidth + 1;
          return (
            <g key={bin.start}>
              <title>{`${bin.start}–${bin.end} days: ${formatCount(bin.all_cases)} cases (${formatCount(bin.most_common_variant)} in the most common variant)`}</title>
              <rect x={x} width={slotWidth - 2} y={y(bin.all_cases)} height={y(bin.most_common_variant) - y(bin.all_cases)} className={styles.barOther} />
              <rect x={x} width={slotWidth - 2} y={y(bin.most_common_variant)} height={y(0) - y(bin.most_common_variant)} className={styles.barTop} />
              {index % tickEvery === 0 ? (
                <text x={x} y={HEIGHT - MARGIN.bottom + 16} className={styles.axisLabel}>
                  {bin.start}
                </text>
              ) : null}
            </g>
          );
        })}

        <g>
          <title>{`${overflow.start} days or longer: ${formatCount(overflow.all_cases)} cases (${formatCount(overflow.most_common_variant)} in the most common variant)`}</title>
          <rect x={overflowX + 1} width={slotWidth - 2} y={y(overflow.all_cases)} height={y(0) - y(overflow.all_cases)} fill="url(#overflow-hatch)" className={styles.barOverflow} />
          <text x={overflowX} y={HEIGHT - MARGIN.bottom + 16} className={styles.axisLabel}>
            ≥{overflow.start}
          </text>
        </g>
        <text x={WIDTH - MARGIN.right} y={HEIGHT - 4} className={styles.axisLabel} textAnchor="end">
          days
        </text>

        {markers.map((marker, index) => {
          const x = xForDays(marker.days);
          // Percentiles close together would print their labels on top of each other; drop every
          // such label one line lower than its left neighbour.
          const crowded = index > 0 && x - xForDays(markers[index - 1].days) < 90;
          return (
            <g key={marker.label}>
              <line x1={x} x2={x} y1={MARGIN.top - 4} y2={y(0)} className={styles.marker} />
              <text x={x + 4} y={MARGIN.top - (crowded ? -6 : 8)} className={styles.markerLabel}>
                {marker.label} {marker.days.toFixed(1)} d
              </text>
            </g>
          );
        })}
      </svg>

      <table className={`${styles.table} ${styles.distributionTable}`}>
        <caption className={styles.caption}>
          Percentiles use linear interpolation. The mean is shown last because long cases pull it
          above the typical case.
        </caption>
        <thead>
          <tr>
            <th scope="col">Cases</th>
            <th scope="col" className={styles.numeric}>Count</th>
            <th scope="col" className={styles.numeric}>p50</th>
            <th scope="col" className={styles.numeric}>p90</th>
            <th scope="col" className={styles.numeric}>p99</th>
            <th scope="col" className={styles.numeric}>Max</th>
            <th scope="col" className={styles.numeric}>Mean</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, stats]) =>
            stats ? (
              <tr key={label}>
                <th scope="row">{label}</th>
                <td className={styles.numeric}>{formatCount(stats.count)}</td>
                <td className={styles.numeric}>{formatDurationSeconds(stats.p50)}</td>
                <td className={styles.numeric}>{formatDurationSeconds(stats.p90)}</td>
                <td className={styles.numeric}>{formatDurationSeconds(stats.p99)}</td>
                <td className={styles.numeric}>{formatDurationSeconds(stats.max)}</td>
                <td className={styles.numeric}>{formatDurationSeconds(stats.mean)}</td>
              </tr>
            ) : null,
          )}
        </tbody>
      </table>
    </div>
  );
}
