"""Written Module B diagnostic report: deterministic, numbers-first Markdown.

01-REQUIREMENTS.md Module B req. 5 and acceptance: every claim cites a number computed from the
data, and the report answers three questions: what share of cases deviate from the intended path,
which single transition costs the most aggregate time, and how much total cycle time rework adds.
As with the Module A summary, no LLM is involved (02-TECH-STACK-AND-SKILLS.md): each sentence is a
fixed template filled with computed values, so the same data always yields the same document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from meridian.conformance.bottlenecks import (
    BottleneckAnalysis,
    BottleneckKind,
)
from meridian.conformance.rework import ReworkAnalysis
from meridian.discovery.summary import format_duration, lifecycle_caveat, lifecycle_label
from meridian.ingestion.lifecycle import LifecyclePolicy

TOP_ROWS = 5
SECONDS_PER_DAY = 86_400

KIND_LABELS = {
    BottleneckKind.UNIFORMLY_SLOW.value: "uniformly slow",
    BottleneckKind.HIGH_VARIANCE.value: "high variance",
    BottleneckKind.SLOW_AND_VARIABLE.value: "slow and high variance",
    BottleneckKind.NOT_FLAGGED.value: "not flagged",
    BottleneckKind.INSUFFICIENT_DATA.value: "not classified (too few occurrences)",
}

# Why these explanations are fixed text: they restate the requirement's reason for separating the
# kinds (different causes, different fixes), not a judgement about any particular transition.
KIND_MEANINGS = {
    BottleneckKind.UNIFORMLY_SLOW: (
        "Nearly every case waits a long time here, which points at capacity, batching or policy: "
        "a fix applies to the step for everyone."
    ),
    BottleneckKind.HIGH_VARIANCE: (
        "Most cases pass quickly but some get stuck, which points at exceptions, missing "
        "information or prioritisation: a fix starts from what the stuck cases share."
    ),
    BottleneckKind.SLOW_AND_VARIABLE: (
        "The typical case waits long and the spread is wide, so both a general cause and "
        "case-specific exceptions are likely."
    ),
}


@dataclass(frozen=True)
class DiagnosticInputs:
    """Everything the report is generated from, already computed.

    `conformance` is the summary written by the conformance run (reference description, token
    aggregates, fitness by outcome), so the report states exactly what was measured against.
    """

    dataset_name: str
    lifecycle: LifecyclePolicy | None
    conformance: dict[str, Any]
    bottlenecks: BottleneckAnalysis
    rework: ReworkAnalysis


def _aggregate_time(seconds: float) -> str:
    """Time summed across cases: case-days with separators, or case-hours for less than a day.

    Why "case-" units: the figure adds up time spent by many cases in parallel, so it is not
    calendar time, and naming it that way stops it being misread as elapsed days.
    """
    if seconds < SECONDS_PER_DAY:
        return f"{seconds / 3_600:.1f} case-hours"
    return f"{seconds / SECONDS_PER_DAY:,.0f} case-days"


def _plural(count: int, singular: str, plural: str) -> str:
    """Return "1 case" / "2 cases" with thousands separators."""
    return f"{count:,} {singular if count == 1 else plural}"


def render_diagnostic_report(inputs: DiagnosticInputs) -> str:
    """Render the report: the three answers first, then the evidence behind each, then caveats."""
    sections = [
        _title(inputs),
        _answers(inputs),
        _conformance_section(inputs),
        _bottleneck_section(inputs),
        _rework_section(inputs),
        _caveats(inputs),
    ]
    return "\n\n".join(sections).rstrip() + "\n"


def _title(inputs: DiagnosticInputs) -> str:
    """Title and scope."""
    summary = inputs.conformance
    return (
        f"# Process diagnosis — {inputs.dataset_name}\n\n"
        f"Computed from {summary['case_count']:,} cases (lifecycle rule: "
        f"{lifecycle_label(inputs.lifecycle)}). Every figure is computed from the event log; none "
        "is estimated."
    )


def _answers(inputs: DiagnosticInputs) -> str:
    """The three acceptance questions, each answered in one paragraph that cites its numbers."""
    summary = inputs.conformance
    deviating = round(summary["deviating_share"] * summary["case_count"])
    fitness = summary["case_fitness"]

    top = inputs.bottlenecks.most_costly()
    kind = KIND_LABELS[top.kind]

    rework = inputs.rework
    distribution = rework.rework_time_distribution()

    return "\n\n".join(
        [
            "## The three questions",
            (
                "**1. What share of cases deviate from the intended path?** "
                f"{summary['deviating_share']:.1%} ({deviating:,} of {summary['case_count']:,} "
                "cases) do not follow the reference path exactly. Log fitness is "
                f"{summary['log_fitness']:.3f} and the median case fitness is "
                f"{fitness['p50']:.3f}, "
                "where 1 means the case follows the reference exactly. "
                f"Reference: {summary['reference']['description']} "
                f"{_reference_path_outcomes(summary)}"
            ),
            (
                "**2. Which single transition costs the most aggregate time?** "
                f"`{top.source}` → `{top.target}`: {_aggregate_time(top.total_seconds)}, "
                f"{top.share_of_total_time:.1%} of all elapsed time between events, over "
                f"{_plural(int(top.occurrences), 'occurrence', 'occurrences')}. Its median wait is "
                f"{format_duration(top.p50_seconds)}, with the middle half of cases between "
                f"{format_duration(top.q1_seconds)} and {format_duration(top.q3_seconds)}; "
                f"bottleneck classification: {kind}."
            ),
            _rework_answer(rework, distribution),
        ]
    )


def _reference_path_outcomes(summary: dict[str, Any]) -> str:
    """State how the cases that follow the reference path exactly end.

    Why this is part of the first answer: if the most common path ends in cancellation rather than
    approval, that is a diagnostic finding about the process itself, and it changes how "deviating
    from the reference" should be read.
    """
    outcomes = summary.get("reference_path_outcomes") or {}
    total = sum(outcomes.values())
    if not total:
        return "No case follows the reference path exactly."
    mix = ", ".join(f"{label} {count / total:.0%}" for label, count in outcomes.items())
    return f"The {_plural(total, 'case', 'cases')} following the reference path end: {mix}."


def _rework_answer(rework: ReworkAnalysis, distribution: dict[str, float]) -> str:
    """Answer question 3, with a plain statement when no case repeats an activity."""
    question = "**3. How much total cycle time does rework add?** "
    if rework.cases_with_rework == 0:
        return question + "No case repeats an activity, so rework adds no cycle time."
    return (
        question
        + f"{_aggregate_time(rework.total_rework_seconds)}, {rework.rework_time_share:.1%} of all "
        + "recorded cycle time, sit inside rework loops, across "
        + f"{_plural(rework.cases_with_rework, 'case', 'cases')} "
        + f"({rework.rework_case_share:.1%} of cases). Among those cases, rework time has a "
        + f"median of {format_duration(distribution['p50'])} and a p90 of "
        + f"{format_duration(distribution['p90'])}."
    )


def _conformance_section(inputs: DiagnosticInputs) -> str:
    """Reference model, token-replay aggregates and fitness by outcome."""
    summary = inputs.conformance
    reference = summary["reference"]
    fitness = summary["case_fitness"]
    path = " → ".join(f"`{activity}`" for activity in reference["activities"])
    rows = [
        "| Measure | Value |",
        "|---|---:|",
        f"| Cases replayed | {summary['case_count']:,} |",
        f"| Cases following the reference exactly | {summary['fitting_cases']:,} |",
        f"| Cases deviating | {summary['deviating_share']:.1%} |",
        f"| Log fitness (pooled token counts) | {summary['log_fitness']:.3f} |",
        f"| Case fitness p10 / p50 / p90 | {fitness['p10']:.3f} / {fitness['p50']:.3f} / "
        f"{fitness['p90']:.3f} |",
        f"| Case fitness mean | {fitness['mean']:.3f} |",
    ]
    outcome_rows = ["| Outcome | Mean case fitness |", "|---|---:|"] + [
        f"| {label} | {value:.3f} |"
        for label, value in summary["mean_case_fitness_by_outcome"].items()
    ]
    return "\n\n".join(
        [
            "## Conformance against the reference model",
            f"Reference strategy `{reference['strategy']}`: {reference['description']}",
            f"Reference path: {path}",
            "\n".join(rows),
            "Mean case fitness by outcome shows which kind of case the reference describes best:",
            "\n".join(outcome_rows),
            f"Fitness formula per case: `{summary['fitness_formula']}`.",
        ]
    )


def _transition_rows(table: pd.DataFrame) -> list[str]:
    """Markdown rows for a bottleneck table excerpt."""
    return [
        f"| `{row.source}` → `{row.target}` | {row.total_seconds / SECONDS_PER_DAY:,.0f} | "
        f"{row.share_of_total_time:.1%} | {row.occurrences:,} | "
        f"{format_duration(row.p50_seconds)} | "
        f"{format_duration(row.q1_seconds)} – {format_duration(row.q3_seconds)} | "
        f"{format_duration(row.p90_seconds)} | {KIND_LABELS[row.kind]} |"
        for row in table.itertuples(index=False)
    ]


def _bottleneck_section(inputs: DiagnosticInputs) -> str:
    """Classification rules, the costliest transitions, and each flagged kind with its meaning."""
    analysis = inputs.bottlenecks
    table = analysis.transitions
    counts = table["kind"].value_counts()
    kind_counts = ", ".join(
        f"{int(counts.get(kind.value, 0))} {KIND_LABELS[kind.value]}" for kind in BottleneckKind
    )
    header = [
        "| Transition | Total case-days | Share of time | Occurrences "
        "| Median | Middle half | p90 | Kind |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    parts = [
        "## Bottlenecks",
        (
            "Wait time is the elapsed time between consecutive events of a case. "
            f"{len(table):,} transitions: {kind_counts}. A transition is slow when its median wait "
            f"is at least {format_duration(analysis.slow_threshold_seconds)} (the 75th percentile "
            "of transition medians) and high variance when its quartile dispersion is at least "
            f"{analysis.dispersion_threshold} (the 75th-percentile wait is at least three times "
            f"the 25th); transitions with fewer than {analysis.min_occurrences} occurrences are "
            "not classified."
        ),
        "Costliest transitions by total time:",
        "\n".join(header + _transition_rows(table.head(TOP_ROWS))),
    ]
    for kind, meaning in KIND_MEANINGS.items():
        flagged = analysis.flagged(kind)
        if flagged.empty:
            continue
        parts.append(
            f"**{KIND_LABELS[kind.value].capitalize()}** ({len(flagged):,} transitions). {meaning}"
        )
        parts.append("\n".join(header + _transition_rows(flagged.head(TOP_ROWS))))
    parts.append("Every transition with its full distribution: `bottlenecks.csv`.")
    return "\n\n".join(parts)


def _rework_section(inputs: DiagnosticInputs) -> str:
    """Cases with rework and the activities repeated most, with the non-additivity caveat."""
    rework = inputs.rework
    lines = [
        "## Rework",
        (
            f"{rework.cases_with_rework:,} of {len(rework.cases):,} cases "
            f"({rework.rework_case_share:.1%}) perform at least one activity more than once, "
            f"putting {_aggregate_time(rework.total_rework_seconds)} "
            f"({rework.rework_time_share:.1%} of all cycle time) inside rework loops."
        ),
    ]
    if not rework.activities.empty:
        rows = [
            "| Activity | Cases | Repetitions | Total span (case-days) | Median span |",
            "|---|---:|---:|---:|---:|",
        ] + [
            f"| `{row.activity}` | {row.cases_with_rework:,} | {row.repeat_occurrences:,} | "
            f"{row.total_span_seconds / SECONDS_PER_DAY:,.0f} | "
            f"{format_duration(row.median_span_seconds)} |"
            for row in rework.activities.head(TOP_ROWS).itertuples(index=False)
        ]
        lines += [
            "Activities repeated across the most time:",
            "\n".join(rows),
            (
                "Spans of different activities overlap within a case, so these activity totals do "
                "not add up to the overall rework time above, which counts each hour once."
            ),
        ]
    lines.append("Per-case and per-activity detail: `rework_cases.csv`, `rework_activities.csv`.")
    return "\n\n".join(lines)


def _caveats(inputs: DiagnosticInputs) -> str:
    """Conditions a reader needs before quoting any number above."""
    caveats = [
        "- Conformance numbers depend on the reference model. The strategy and evidence for the "
        "one used are stated above; a different reference gives different deviation and fitness.",
        "- A repeated activity counts as rework by definition. Some repetitions (for example a "
        "second offer) may be legitimate renegotiation rather than error correction.",
        "- Rework time is attributed as the union of each repeated activity's first-to-last span "
        "in a case. It is time inside loops, not a guaranteed saving if the loops disappeared.",
        "- With one timestamp per event, a wait includes the next activity's own processing time "
        "as well as queueing before it.",
        "- Percentiles use linear interpolation between order statistics.",
    ]
    caveats.insert(0, f"- {lifecycle_caveat(inputs.lifecycle)}")
    return "## Caveats\n\n" + "\n".join(caveats)
