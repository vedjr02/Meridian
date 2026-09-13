"""End-to-end ingestion: verified raw file, parsed events, normalized log, files and database."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import psycopg

from meridian.config import Settings, get_settings
from meridian.datasets import ChecksumMismatchError, download_dataset
from meridian.ingestion.normalize import NormalizationReport, normalize_events
from meridian.ingestion.store import StoredRowCountMismatchError, replace_event_log
from meridian.ingestion.xes import count_raw_events, parse_xes

logger = logging.getLogger(__name__)


class RowCountMismatchError(RuntimeError):
    """Raised when events go missing between the source file and the normalized log.

    Covers both hand-offs checked in `run_ingestion`: file to parser, and parser to normalized
    log plus its exclusion and filter counts.
    """


@dataclass(frozen=True)
class IngestionResult:
    """Everything one ingestion run produced, returned so callers and tests can inspect it."""

    source_path: Path
    source_events: int
    raw_events: pd.DataFrame
    event_log: pd.DataFrame
    report: NormalizationReport
    run_id: int | None


def run_ingestion(settings: Settings, *, load_database: bool = True) -> IngestionResult:
    """Run ingestion end to end, writing processed files and (optionally) loading PostgreSQL.

    Each step guards against a different way data can silently go wrong:
    1. `download_dataset` verifies the file checksum (wrong, changed or truncated input).
    2. The independent byte count must equal the parsed row count (parser skipping events).
    3. The normalization report must account for every parsed event (rows dropped without a
       recorded reason).
    4. `replace_event_log` re-counts rows inside its transaction (rows lost on the way into
       storage).
    """
    dataset = settings.dataset
    source_path = download_dataset(dataset, settings.raw_dir)

    source_events = count_raw_events(source_path)
    raw_events = parse_xes(source_path)
    if len(raw_events) != source_events:
        raise RowCountMismatchError(
            f"{source_path.name} contains {source_events} <event> elements but the parser "
            f"produced {len(raw_events)} rows ({source_events - len(raw_events)} missing)."
        )
    logger.info(
        "Parsed %d events; matches the independent count of the source file.", len(raw_events)
    )

    event_log, report = normalize_events(
        raw_events,
        lifecycle_keep=settings.lifecycle_transitions,
        outcome_activities=dict(dataset.outcome_activities),
    )
    if not report.is_fully_accounted:
        raise RowCountMismatchError(
            f"Normalization accounts for {report.normalized_events + report.total_excluded} "
            f"+ {report.filtered_by_lifecycle} filtered of {report.parsed_events} parsed events."
        )

    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    raw_events.to_csv(settings.raw_events_csv, index=False)
    event_log.to_csv(settings.event_log_csv, index=False)
    payload = {
        "source": {
            "name": dataset.name,
            "filename": dataset.filename,
            "sha256": dataset.sha256,
            "event_elements": source_events,
        },
        "normalization": report.to_dict(),
    }
    settings.ingestion_report_json.write_text(json.dumps(payload, indent=2) + "\n")

    run_id = None
    if load_database:
        with psycopg.connect(settings.database_url) as conn:
            run_id = replace_event_log(
                conn,
                event_log,
                source_filename=dataset.filename,
                source_sha256=dataset.sha256,
                report=payload,
            )

    return IngestionResult(source_path, source_events, raw_events, event_log, report, run_id)


def format_summary(result: IngestionResult) -> str:
    """Render a run as plain-text lines with every count, for the terminal.

    Why every exclusion reason is listed, including zeros: "0 out-of-order events" is a finding;
    omitting it would leave a reader unsure whether the check ran.
    """
    report = result.report
    lines = [
        f"Source events (independent count): {result.source_events:,}",
        f"Parsed events:                     {report.parsed_events:,} "
        f"({report.parsed_cases:,} cases)",
        f"Normalized events:                 {report.normalized_events:,} "
        f"({report.normalized_cases:,} cases)",
        f"Filtered by lifecycle (kept {report.lifecycle_kept or 'all'}): "
        f"{report.filtered_by_lifecycle:,}",
        f"Excluded as malformed:             {report.total_excluded:,}",
    ]
    lines += [f"  - {reason}: {count:,}" for reason, count in report.excluded.items()]
    lines += [
        f"Normalized events missing resource: {report.events_missing_resource:,}",
        f"Case outcomes: {report.outcome_counts}",
        f"Fully accounted: {report.is_fully_accounted}",
        f"Database run id: {result.run_id if result.run_id is not None else 'not loaded'}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: `python -m meridian.ingestion [--no-db]`.

    Why failures return exit code 1 with a specific message instead of a traceback: the error
    must say what went wrong and how many rows were affected (03-UIUX-RULES.md, error states).
    """
    parser = argparse.ArgumentParser(description="Ingest the raw event log (Module A, step 1).")
    parser.add_argument(
        "--no-db", action="store_true", help="write processed files only; skip PostgreSQL"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        result = run_ingestion(get_settings(), load_database=not args.no_db)
    except (ChecksumMismatchError, RowCountMismatchError, StoredRowCountMismatchError) as exc:
        logger.error("Ingestion failed: %s", exc)
        return 1
    except psycopg.OperationalError as exc:
        logger.error(
            "Could not connect to PostgreSQL (MERIDIAN_DATABASE_URL): %s Processed files were "
            "written; start the server and re-run, or pass --no-db.",
            exc,
        )
        return 1

    print(format_summary(result))
    return 0
