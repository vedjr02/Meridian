"""Module A in one command: raw event log to process map, mined model, variants and summary.

`python -m meridian.discovery` meets Module A's acceptance criterion: given the raw log file, one
command produces (a) a DFG visualization, (b) the mined heuristic process model, (c) a variant
frequency table, and (d) a written cycle-time summary with p50/p90/p99.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import psycopg

from meridian.config import Settings, get_settings
from meridian.datasets import ChecksumMismatchError
from meridian.discovery.cycle_time import (
    CYCLE_TIME,
    DistributionSummary,
    case_statistics,
    summarize_distribution,
)
from meridian.discovery.dfg import build_dfg
from meridian.discovery.heuristic_miner import mine_heuristic_net
from meridian.discovery.summary import DiscoveryInputs, format_duration, render_summary
from meridian.discovery.variants import analyze_variants
from meridian.discovery.visualize import dfg_to_mermaid
from meridian.ingestion.io import read_event_log_csv
from meridian.ingestion.pipeline import RowCountMismatchError, run_ingestion
from meridian.ingestion.store import StoredRowCountMismatchError

logger = logging.getLogger(__name__)

COVERAGE_SHARE = 0.8


@dataclass(frozen=True)
class DiscoveryResult:
    """What one discovery run produced: every output path and the headline numbers."""

    outputs: dict[str, Path]
    ingested: bool
    case_count: int
    variant_count: int
    variants_to_cover: int
    cycle_time: DistributionSummary


def lifecycle_description(settings: Settings) -> str:
    """Describe which lifecycle transitions the event log on disk contains.

    Why the ingestion report rather than the current setting: the CSV may have been written under
    a different `MERIDIAN_LIFECYCLE_TRANSITIONS` than the one set now, and the summary must
    describe the data it was actually computed from.
    """
    try:
        report = json.loads(settings.ingestion_report_json.read_text())
        kept = report["normalization"]["lifecycle_kept"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return "unknown (no ingestion report found)"
    return "all" if kept is None else ", ".join(kept)


def run_discovery(
    settings: Settings, *, reingest: bool = False, load_database: bool = True
) -> DiscoveryResult:
    """Run every Module A step and write all outputs to the processed data directory.

    Ingestion runs first only when no normalized log exists yet or `reingest` is set, so repeated
    discovery runs (for example while tuning the dependency threshold) take seconds instead of
    re-parsing 1.2M events each time.
    """
    ingested = reingest or not settings.event_log_csv.exists()
    if ingested:
        run_ingestion(settings, load_database=load_database)

    event_log = read_event_log_csv(settings.event_log_csv)
    dfg = build_dfg(event_log)
    net = mine_heuristic_net(event_log, settings.dependency_threshold)
    variants = analyze_variants(event_log)
    stats = case_statistics(event_log, variants)
    diagram = dfg_to_mermaid(dfg)
    summary = render_summary(
        DiscoveryInputs(
            dataset_name=settings.dataset.name,
            dfg=dfg,
            net=net,
            variants=variants,
            case_stats=stats,
            diagram=diagram,
            lifecycle_kept=lifecycle_description(settings),
            coverage_share=COVERAGE_SHARE,
        )
    )

    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    dfg.edges.to_csv(settings.dfg_edges_csv, index=False)
    settings.dfg_mermaid.write_text(diagram.text)
    settings.heuristic_net_json.write_text(json.dumps(net.to_dict(), indent=2) + "\n")
    variants.variants.to_csv(settings.variants_csv, index=False)
    stats.to_csv(settings.case_statistics_csv, index=False)
    settings.discovery_summary_md.write_text(summary)

    return DiscoveryResult(
        outputs={
            "DFG visualization": settings.dfg_mermaid,
            "DFG edges": settings.dfg_edges_csv,
            "Heuristic model": settings.heuristic_net_json,
            "Variant table": settings.variants_csv,
            "Case statistics": settings.case_statistics_csv,
            "Written summary": settings.discovery_summary_md,
        },
        ingested=ingested,
        case_count=variants.case_count,
        variant_count=variants.variant_count,
        variants_to_cover=variants.variants_to_cover(COVERAGE_SHARE),
        cycle_time=summarize_distribution(stats[CYCLE_TIME]),
    )


def format_result(result: DiscoveryResult) -> str:
    """Render the headline numbers and output locations for the terminal."""
    cycle = result.cycle_time
    lines = [
        f"Cases: {result.case_count:,}   Variants: {result.variant_count:,}   "
        f"Variants covering {COVERAGE_SHARE:.0%} of cases: {result.variants_to_cover:,}",
        f"Cycle time p50 {format_duration(cycle.p50)}, p90 {format_duration(cycle.p90)}, "
        f"p99 {format_duration(cycle.p99)} (mean {format_duration(cycle.mean)})",
        "Outputs:",
    ]
    lines += [f"  {label}: {path}" for label, path in result.outputs.items()]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: `python -m meridian.discovery [--reingest] [--no-db]`.

    Why ingestion errors are caught here too: when this command triggers ingestion, a failure
    must still say what went wrong and how many rows were affected, not print a traceback.
    """
    parser = argparse.ArgumentParser(description="Run Module A process discovery end to end.")
    parser.add_argument(
        "--reingest", action="store_true", help="re-run ingestion even if a normalized log exists"
    )
    parser.add_argument(
        "--no-db", action="store_true", help="when ingestion runs, skip loading PostgreSQL"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        result = run_discovery(get_settings(), reingest=args.reingest, load_database=not args.no_db)
    except (ChecksumMismatchError, RowCountMismatchError, StoredRowCountMismatchError) as exc:
        logger.error("Ingestion failed: %s", exc)
        return 1
    except psycopg.OperationalError as exc:
        logger.error("Could not connect to PostgreSQL: %s Re-run with --no-db to skip it.", exc)
        return 1

    print(format_result(result))
    return 0
