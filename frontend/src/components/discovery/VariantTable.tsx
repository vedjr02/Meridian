"use client";

import { formatCount, formatShare } from "@/lib/format";
import type { Variant, VariantList } from "@/lib/discovery";

import styles from "./discovery.module.css";

// Muted status colours for known BPI 2017 outcomes. Colour is never the only signal: the outcome
// name and share are always printed next to the swatch (03-UIUX-RULES.md §5).
const OUTCOME_TONES: Record<string, string> = {
  pending: styles.toneLow,
  cancelled: styles.toneMedium,
  denied: styles.toneHigh,
};

type VariantTableProps = {
  variants: VariantList;
  selectedRank: number | null;
  onSelect: (rank: number | null) => void;
};

/** Outcome mix of one variant, most frequent first, as labelled swatches. */
function OutcomeMix({ variant }: { variant: Variant }) {
  const entries = Object.entries(variant.outcomes).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  return (
    <ul className={styles.outcomes}>
      {entries.map(([label, count]) => (
        <li key={label}>
          <span className={`${styles.swatch} ${OUTCOME_TONES[label] ?? styles.toneNeutral}`} aria-hidden="true" />
          {label} {Math.round((count / variant.case_count) * 100)}%
        </li>
      ))}
    </ul>
  );
}

/**
 * Most frequent variants, beside the map so a path can be cross-referenced without scrolling
 * (03-UIUX-RULES.md §3). Selecting a row highlights that variant's path on the map; the selected
 * variant's full activity sequence is listed under the table.
 */
export default function VariantTable({ variants, selectedRank, onSelect }: VariantTableProps) {
  const selected = variants.variants.find((variant) => variant.rank === selectedRank) ?? null;

  return (
    <div className={styles.variantFrame}>
      <div className={styles.tableScroll}>
        <table className={styles.table}>
          <caption className={styles.caption}>
            Top {variants.variants.length} of {formatCount(variants.variant_count)} variants. Select
            one to highlight its path.
          </caption>
          <thead>
            <tr>
              <th scope="col">Rank</th>
              <th scope="col" className={styles.numeric}>Cases</th>
              <th scope="col">Cumulative</th>
              <th scope="col">Outcomes</th>
            </tr>
          </thead>
          <tbody>
            {variants.variants.map((variant) => {
              const isSelected = variant.rank === selectedRank;
              return (
                <tr key={variant.rank} className={isSelected ? styles.rowSelected : undefined}>
                  <td>
                    <button
                      type="button"
                      className={styles.rankButton}
                      aria-pressed={isSelected}
                      aria-label={`Variant ${variant.rank}: ${isSelected ? "remove highlight" : "highlight path on the map"}`}
                      onClick={() => onSelect(isSelected ? null : variant.rank)}
                    >
                      #{variant.rank}
                    </button>
                    <span className={styles.cellNote}>{variant.activities.length} steps</span>
                  </td>
                  <td className={styles.numeric}>
                    {formatCount(variant.case_count)}
                    <span className={styles.cellNote}>{formatShare(variant.case_share)}</span>
                  </td>
                  <td>
                    <span className={styles.cumulative}>
                      <span className={styles.cumulativeBar} style={{ width: `${variant.cumulative_share * 100}%` }} aria-hidden="true" />
                      <span className={styles.cumulativeText}>{formatShare(variant.cumulative_share)}</span>
                    </span>
                  </td>
                  <td>
                    <OutcomeMix variant={variant} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selected ? (
        <div className={styles.sequence} aria-live="polite">
          <div className={styles.sequenceHeader}>
            <h3>Variant #{selected.rank} path</h3>
            <button type="button" className={styles.textButton} onClick={() => onSelect(null)}>
              Clear highlight
            </button>
          </div>
          <ol>
            {selected.activities.map((activity, index) => (
              <li key={`${index}-${activity}`}>{activity}</li>
            ))}
          </ol>
        </div>
      ) : (
        <p className={styles.sequenceHint}>
          No variant selected. The map shows every edge the miner kept.
        </p>
      )}
    </div>
  );
}
