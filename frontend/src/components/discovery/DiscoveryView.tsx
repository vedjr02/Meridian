"use client";

import { useState } from "react";

import { formatCount, formatDurationSeconds, formatShare } from "@/lib/format";
import type { DiscoveryData } from "@/lib/discovery";

import CycleTimeHistogram from "./CycleTimeHistogram";
import ProcessMap from "./ProcessMap";
import VariantTable from "./VariantTable";
import styles from "./discovery.module.css";

/**
 * Module A screen layout: headline numbers first, then the process map as the hero element with the
 * variant table beside it, then the cycle-time distribution (03-UIUX-RULES.md §3). The selected
 * variant is the only shared state, linking the table to the map.
 */
export default function DiscoveryView({ data }: { data: DiscoveryData }) {
  const [selectedRank, setSelectedRank] = useState<number | null>(null);
  const { overview, processMap, variants, histogram } = data;
  const selected = variants.variants.find((variant) => variant.rank === selectedRank) ?? null;
  const cycle = overview.cycle_time_seconds.all_cases;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <p className={styles.eyebrow}>Module A · Process discovery</p>
          <h1 className={styles.title}>{overview.dataset}</h1>
          <p className={styles.scope}>
            {formatCount(overview.case_count)} cases · {formatCount(overview.event_count)} events ·{" "}
            {overview.activity_count} activities · measured from the event log, not estimated
          </p>
        </div>
        <dl className={styles.stats}>
          <div className={styles.stat}>
            <dt>Variants covering {Math.round(overview.coverage_share * 100)}% of cases</dt>
            <dd>
              {formatCount(overview.variants_to_cover)}
              <span> of {formatCount(overview.variant_count)} distinct</span>
            </dd>
          </div>
          <div className={styles.stat}>
            <dt>Most common variant</dt>
            <dd>
              {formatShare(overview.top_variant_share)}
              <span> of cases</span>
            </dd>
          </div>
          <div className={styles.stat}>
            <dt>Cycle time, all cases</dt>
            <dd className={styles.range}>
              p50 {formatDurationSeconds(cycle.p50)}
              <span> · p90 {formatDurationSeconds(cycle.p90)} · p99 {formatDurationSeconds(cycle.p99)}</span>
            </dd>
          </div>
        </dl>
      </header>

      <p className={styles.caveat} role="note">
        <span className={styles.caveatTag}>Caveat</span>
        {overview.lifecycle.caveat}
        {overview.open_case_count > 0
          ? ` ${formatCount(overview.open_case_count)} cases had not finished when the log was extracted; their cycle times are lower bounds.`
          : ""}
      </p>

      <div className={styles.workspace}>
        <section className={styles.panel} aria-labelledby="map-title">
          <div className={styles.panelHeader}>
            <h2 id="map-title">Mined process model</h2>
            <p>
              Heuristic miner at dependency threshold {processMap.threshold} · line width encodes
              transition frequency · hover an edge for counts and timing
            </p>
          </div>
          <ProcessMap map={processMap} highlight={selected?.activities ?? null} />
        </section>

        <section className={styles.panel} aria-labelledby="variants-title">
          <div className={styles.panelHeader}>
            <h2 id="variants-title">Variants</h2>
            <p>
              The most common variant ends{" "}
              {Object.keys(variants.variants[0]?.outcomes ?? {}).join(", ") || "without an outcome"}
              : it is the most frequent path, not necessarily a successful one.
            </p>
          </div>
          <VariantTable variants={variants} selectedRank={selectedRank} onSelect={setSelectedRank} />
        </section>
      </div>

      <section className={styles.panel} aria-labelledby="cycle-title">
        <CycleTimeHistogram histogram={histogram} overview={overview} />
      </section>
    </div>
  );
}
