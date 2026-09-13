"""Module B in one command: conformance, bottlenecks, rework and the written diagnostic report.

`python -m meridian.conformance` measures conformance against the most frequent variant overall,
as 01-REQUIREMENTS.md specifies and Ved confirmed on 2026-09-13 (08-OPEN-QUESTIONS.md); other
strategies stay available via `--reference`. Every output records which reference was used.
Bottleneck and rework analysis do not depend on the reference and run in the same command so the
report is complete.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from meridian.config import Settings, get_settings
from meridian.conformance.bottlenecks import BottleneckAnalysis, analyze_bottlenecks
from meridian.conformance.reference import (
    ReferenceModel,
    ReferenceStrategy,
    select_reference_model,
)
from meridian.conformance.replay import FITNESS, FITS, LogReplay, replay_log
from meridian.conformance.report import DiagnosticInputs, render_diagnostic_report
from meridian.conformance.rework import ReworkAnalysis, analyze_rework
from meridian.discovery.pipeline import recorded_lifecycle_policy
from meridian.discovery.summary import NO_OUTCOME, format_duration
from meridian.ingestion import schema
from meridian.ingestion.io import read_event_log_csv
from meridian.ingestion.lifecycle import LifecyclePolicy

FITNESS_FORMULA = "0.5 * (1 - missing / consumed) + 0.5 * (1 - remaining / produced)"


@dataclass(frozen=True)
class ConformanceResult:
    """What one conformance run produced: the reference used, the replay, and output paths."""

    reference: ReferenceModel
    replay: LogReplay
    summary: dict[str, Any]
    outputs: dict[str, Path]


@dataclass(frozen=True)
class DiagnosisResult:
    """The full Module B run: conformance, bottlenecks, rework, the report text and all outputs."""

    conformance: ConformanceResult
    bottlenecks: BottleneckAnalysis
    rework: ReworkAnalysis
    report: str
    outputs: dict[str, Path]


def _policy_value(policy: LifecyclePolicy | None) -> str | None:
    """JSON value for a recorded lifecycle policy (None when no ingestion report exists)."""
    return policy.value if policy else None


def _load_event_log(settings: Settings) -> pd.DataFrame:
    """Read the normalized event log, or explain which command produces it."""
    if not settings.event_log_csv.exists():
        raise FileNotFoundError(
            f"No normalized event log at {settings.event_log_csv}; "
            "run `python -m meridian.discovery` first."
        )
    return read_event_log_csv(settings.event_log_csv)


def _fitness_by_outcome(event_log: pd.DataFrame, replay: LogReplay) -> dict[str, float]:
    """Mean case fitness per outcome, so a reader can see which kind of case the reference suits.

    Why this is reported: on BPI 2017 it is what exposes a misleading reference. If successful
    cases fit worst, the "intended path" is not an intended path.
    """
    outcomes = (
        event_log.drop_duplicates(schema.CASE_ID)
        .set_index(schema.CASE_ID)[schema.OUTCOME]
        .astype("object")
    )
    labels = replay.cases[schema.CASE_ID].map(outcomes)
    labels = labels.where(labels.notna(), NO_OUTCOME)
    means = replay.cases[FITNESS].groupby(labels).mean()
    return {str(label): float(value) for label, value in sorted(means.items())}


def _fitting_case_outcomes(event_log: pd.DataFrame, replay: LogReplay) -> dict[str, int]:
    """Outcome counts of the cases that follow the reference path exactly.

    Why: how the reference path itself ends is a finding in its own right. On BPI 2017's
    `complete`-only log the modal path ended in cancellation, which Ved asked to be reported rather
    than routed around.
    """
    fitting = replay.cases.loc[replay.cases[FITS], schema.CASE_ID]
    outcomes = (
        event_log.drop_duplicates(schema.CASE_ID)
        .set_index(schema.CASE_ID)[schema.OUTCOME]
        .astype("object")
    )
    labels = fitting.map(outcomes)
    labels = labels.where(labels.notna(), NO_OUTCOME)
    counts = labels.value_counts()
    return {
        str(label): int(count)
        for label, count in sorted(counts.items(), key=lambda i: (-i[1], i[0]))
    }


def run_conformance(
    settings: Settings,
    strategy: ReferenceStrategy,
    *,
    outcome: str | None = None,
    documented_activities: list[str] | None = None,
    event_log: pd.DataFrame | None = None,
) -> ConformanceResult:
    """Select the reference model, replay the normalized log against it, and write both outputs.

    The summary records the reference's strategy, description and activities alongside the
    lifecycle filter of the data, so the numbers can never be separated from what they measure.
    `event_log` lets a caller that already loaded the log avoid reading it twice.
    """
    log = _load_event_log(settings) if event_log is None else event_log
    reference = select_reference_model(
        log, strategy, outcome=outcome, documented_activities=documented_activities
    )
    replay = replay_log(log, reference.net)

    summary = {
        "reference": {
            "strategy": reference.strategy.value,
            "outcome": outcome,
            "description": reference.description,
            "activities": list(reference.activities),
            "supporting_cases": reference.supporting_cases,
            "eligible_cases": reference.eligible_cases,
        },
        "lifecycle_policy": _policy_value(recorded_lifecycle_policy(settings)),
        "fitness_formula": FITNESS_FORMULA,
        "case_count": replay.case_count,
        "fitting_cases": replay.fitting_cases,
        "deviating_share": replay.deviating_share,
        "log_fitness": replay.log_fitness,
        "case_fitness": replay.case_fitness_summary(),
        "mean_case_fitness_by_outcome": _fitness_by_outcome(log, replay),
        "reference_path_outcomes": _fitting_case_outcomes(log, replay),
    }

    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    replay.cases.to_csv(settings.conformance_cases_csv, index=False)
    settings.conformance_summary_json.write_text(json.dumps(summary, indent=2) + "\n")
    return ConformanceResult(
        reference=reference,
        replay=replay,
        summary=summary,
        outputs={
            "Per-case replay": settings.conformance_cases_csv,
            "Conformance summary": settings.conformance_summary_json,
        },
    )


def run_diagnosis(
    settings: Settings,
    strategy: ReferenceStrategy,
    *,
    outcome: str | None = None,
    documented_activities: list[str] | None = None,
) -> DiagnosisResult:
    """Run every Module B analysis on the normalized log and write tables plus the written report.

    The log is read once and shared, so conformance, bottlenecks and rework are guaranteed to
    describe exactly the same events.
    """
    event_log = _load_event_log(settings)
    conformance = run_conformance(
        settings,
        strategy,
        outcome=outcome,
        documented_activities=documented_activities,
        event_log=event_log,
    )
    bottlenecks = analyze_bottlenecks(event_log)
    rework = analyze_rework(event_log)
    report = render_diagnostic_report(
        DiagnosticInputs(
            dataset_name=settings.dataset.name,
            lifecycle=recorded_lifecycle_policy(settings),
            conformance=conformance.summary,
            bottlenecks=bottlenecks,
            rework=rework,
        )
    )

    bottlenecks.transitions.to_csv(settings.bottlenecks_csv, index=False)
    rework.cases.to_csv(settings.rework_cases_csv, index=False)
    rework.activities.to_csv(settings.rework_activities_csv, index=False)
    settings.diagnostic_report_md.write_text(report)
    return DiagnosisResult(
        conformance=conformance,
        bottlenecks=bottlenecks,
        rework=rework,
        report=report,
        outputs=conformance.outputs
        | {
            "Bottlenecks": settings.bottlenecks_csv,
            "Rework by case": settings.rework_cases_csv,
            "Rework by activity": settings.rework_activities_csv,
            "Diagnostic report": settings.diagnostic_report_md,
        },
    )


def format_result(result: DiagnosisResult) -> str:
    """Render the reference used and the three headline answers for the terminal."""
    summary = result.conformance.summary
    fitness = summary["case_fitness"]
    top = result.bottlenecks.most_costly()
    rework = result.rework
    lines = [
        f"Reference ({summary['reference']['strategy']}): {summary['reference']['description']}",
        f"Cases fitting exactly: {summary['fitting_cases']:,} of {summary['case_count']:,} "
        f"({summary['deviating_share']:.1%} deviate)",
        f"Log fitness: {summary['log_fitness']:.3f}   Case fitness p10 {fitness['p10']:.3f}, "
        f"p50 {fitness['p50']:.3f}, p90 {fitness['p90']:.3f} (mean {fitness['mean']:.3f})",
        f"Costliest transition: {top.source} -> {top.target}, "
        f"{top.share_of_total_time:.1%} of elapsed time, median {format_duration(top.p50_seconds)}",
        f"Rework: {rework.rework_time_share:.1%} of cycle time in "
        f"{rework.cases_with_rework:,} cases",
        "Outputs:",
    ]
    lines += [f"  {label}: {path}" for label, path in result.outputs.items()]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: `python -m meridian.conformance [--reference STRATEGY] [...]`.

    Why selection errors return exit code 1 with the message rather than a traceback: an unknown
    outcome or a missing flag is a usage problem the message fully explains.
    """
    parser = argparse.ArgumentParser(
        description="Module B diagnosis: conformance, bottlenecks, rework and written report."
    )
    parser.add_argument(
        "--reference",
        default=ReferenceStrategy.MOST_FREQUENT_VARIANT.value,
        choices=[strategy.value for strategy in ReferenceStrategy],
        help="how to choose the reference model (default: most_frequent_variant, per requirements)",
    )
    parser.add_argument("--outcome", help="outcome for most_frequent_variant_for_outcome")
    parser.add_argument(
        "--documented-activity",
        action="append",
        dest="documented_activities",
        help="one activity of a documented reference, in order; repeat for each (documented only)",
    )
    args = parser.parse_args(argv)

    try:
        result = run_diagnosis(
            get_settings(),
            ReferenceStrategy(args.reference),
            outcome=args.outcome,
            documented_activities=args.documented_activities,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Diagnosis run failed: {exc}", file=sys.stderr)
        return 1
    print(format_result(result))
    return 0
