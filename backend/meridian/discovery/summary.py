"""Written Module A summary: a deterministic, numbers-first Markdown report.

No LLM is involved (02-TECH-STACK-AND-SKILLS.md): every sentence is a fixed template filled with
numbers computed by the discovery modules, so the same data always produces the same document,
and every claim in it can be traced to a computed value.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from meridian.discovery.cycle_time import (
    CYCLE_TIME,
    IS_HAPPY_PATH,
    DistributionSummary,
    summarize_distribution,
)
from meridian.discovery.dfg import DirectlyFollowsGraph
from meridian.discovery.heuristic_miner import (
    BEST_CONNECTION,
    CAUSAL,
    KIND,
    LENGTH_ONE_LOOP,
    LENGTH_TWO_LOOP,
    HeuristicNet,
)
from meridian.discovery.variants import (
    CASE_COUNT,
    CASE_SHARE,
    CUMULATIVE_SHARE,
    LENGTH,
    VARIANT,
    VARIANT_RANK,
    VariantAnalysis,
)
from meridian.discovery.visualize import MermaidDiagram
from meridian.ingestion import schema
from meridian.ingestion.lifecycle import LifecyclePolicy

TOP_VARIANTS_SHOWN = 5
NO_OUTCOME = "no terminal state"


@dataclass(frozen=True)
class DiscoveryInputs:
    """Everything the summary is generated from, computed beforehand by the discovery modules.

    `lifecycle` is the policy ingestion recorded for this log (None if unknown), not the current
    setting, because the summary must describe the data it was computed from.
    """

    dataset_name: str
    dfg: DirectlyFollowsGraph
    net: HeuristicNet
    variants: VariantAnalysis
    case_stats: pd.DataFrame
    diagram: MermaidDiagram
    lifecycle: LifecyclePolicy | None
    coverage_share: float = 0.8


def format_duration(seconds: float) -> str:
    """Render a duration for a reader: days with one decimal, or hours below one day."""
    if seconds < 86_400:
        return f"{seconds / 3_600:.1f} h"
    return f"{seconds / 86_400:.1f} days"


def format_measure(value: float) -> str:
    """Render a dependency or loop measure with three decimals, never as a certain-looking 1.000.

    Why: every heuristic-miner measure is strictly below 1 by construction (the +1 in each
    denominator), so printing 0.99987 as "1.000" would claim a certainty the evidence cannot give.
    """
    return ">0.999" if value >= 0.9995 else f"{value:.3f}"


def lifecycle_label(lifecycle: LifecyclePolicy | None) -> str:
    """Name the lifecycle rule for a scope line, or say it is unknown."""
    return lifecycle.description if lifecycle else "unknown (no ingestion report found)"


def lifecycle_caveat(lifecycle: LifecyclePolicy | None) -> str:
    """The lifecycle caveat for a report, including the case where the rule is unknown."""
    if lifecycle is None:
        return (
            "The lifecycle rule used to build this log is unknown (no ingestion report found), so "
            "it is unclear whether durations run between starts, completions or both."
        )
    return f"Lifecycle rule: {lifecycle.description}. {lifecycle.caveat}"


def _plural(count: int, singular: str, plural: str) -> str:
    """Return "1 variant" / "2 variants" with thousands separators."""
    return f"{count:,} {singular if count == 1 else plural}"


def _outcomes(case_stats: pd.DataFrame) -> pd.Series:
    """Per-case outcome labels with missing outcomes named, so they are counted, not dropped."""
    return (
        case_stats[schema.OUTCOME]
        .astype("object")
        .where(case_stats[schema.OUTCOME].notna(), NO_OUTCOME)
    )


def _outcome_mix(outcomes: pd.Series) -> str:
    """Describe an outcome distribution as "cancelled 100%" or "pending 60%, denied 40%"."""
    shares = outcomes.value_counts(normalize=True)
    ordered = sorted(shares.items(), key=lambda item: (-item[1], str(item[0])))
    return ", ".join(f"{label} {share:.0%}" for label, share in ordered)


def render_summary(inputs: DiscoveryInputs) -> str:
    """Render the full summary: headline, variants, cycle time, process map, model, caveats."""
    sections = [
        _header(inputs),
        _headline(inputs),
        _variants_section(inputs),
        _cycle_time_section(inputs),
        _process_map_section(inputs),
        _model_section(inputs),
        _caveats_section(inputs),
    ]
    return "\n\n".join(sections).rstrip() + "\n"


def _header(inputs: DiscoveryInputs) -> str:
    """Title and the scope every later number refers to."""
    events = sum(inputs.dfg.activity_counts.values())
    return (
        f"# Process discovery summary — {inputs.dataset_name}\n\n"
        f"Computed from {events:,} events in {inputs.variants.case_count:,} cases across "
        f"{len(inputs.dfg.activity_counts)} activities (lifecycle rule: "
        f"{lifecycle_label(inputs.lifecycle)}). Every figure is computed from the event log; none "
        "is estimated."
    )


def _headline(inputs: DiscoveryInputs) -> str:
    """The variant-coverage finding (01-REQUIREMENTS.md Module A requirement 5), in numbers only."""
    variants = inputs.variants
    table = variants.variants
    needed = variants.variants_to_cover(inputs.coverage_share)
    total = variants.variant_count
    singletons = int((table[CASE_COUNT] == 1).sum())
    return (
        "## Headline\n\n"
        f"**Covering {inputs.coverage_share:.0%} of cases takes {needed:,} of "
        f"{_plural(total, 'distinct variant', 'distinct variants')} "
        f"({needed / total:.1%} of all variants).** "
        f"The most common variant accounts for {table[CASE_SHARE].iloc[0]:.1%} of cases, and "
        f"{_plural(singletons, 'variant was', 'variants were')} followed by a single case "
        f"({singletons / total:.1%} of variants)."
    )


def _variants_section(inputs: DiscoveryInputs) -> str:
    """Top variants with their outcome mix, and the most common variant within each outcome."""
    table = inputs.variants.variants
    stats = inputs.case_stats
    outcomes = _outcomes(stats)

    rows = [
        "| Rank | Cases | Share | Cumulative | Activities | Outcomes |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    for variant in table.head(TOP_VARIANTS_SHOWN).itertuples(index=False):
        rank = getattr(variant, VARIANT_RANK)
        mix = _outcome_mix(outcomes[stats[VARIANT_RANK] == rank])
        rows.append(
            f"| {rank} | {getattr(variant, CASE_COUNT):,} | {getattr(variant, CASE_SHARE):.1%} "
            f"| {getattr(variant, CUMULATIVE_SHARE):.1%} | {getattr(variant, LENGTH)} | {mix} |"
        )

    lines = [
        "## Variants",
        "\n".join(rows),
        f"Most common variant: `{table[VARIANT].iloc[0]}`",
        "Most common variant within each outcome:",
    ]
    by_outcome = []
    for label, count in sorted(
        outcomes.value_counts().items(), key=lambda item: (-item[1], str(item[0]))
    ):
        ranks = stats.loc[outcomes == label, VARIANT_RANK].value_counts()
        top_count = int(ranks.max())
        top_rank = int(ranks[ranks == top_count].index.min())
        by_outcome.append(
            f"- {label}: rank {top_rank}, {_plural(top_count, 'case', 'cases')} "
            f"({top_count / count:.1%} of {count:,} {label} cases)"
        )
    lines.append("\n".join(by_outcome))
    lines.append("All variants with their full activity sequences: `variants.csv`.")
    return "\n\n".join(lines)


def _distribution_row(label: str, summary: DistributionSummary) -> str:
    """One table row of cycle-time statistics."""
    values = [summary.p50, summary.p90, summary.p99, summary.mean, summary.maximum]
    cells = " | ".join(format_duration(value) for value in values)
    return f"| {label} | {summary.count:,} | {cells} |"


def _cycle_time_section(inputs: DiscoveryInputs) -> str:
    """Cycle-time distribution overall and for the most common variant versus all others.

    Why the mean is compared to the median in words: acceptance criterion (d) asks for the
    distribution, not the mean, and saying which way the mean is pulled explains why the median
    is the number to quote for a typical case.
    """
    stats = inputs.case_stats
    overall = summarize_distribution(stats[CYCLE_TIME])
    rows = [
        "| Cases | Count | p50 | p90 | p99 | Mean | Max |",
        "|---|---:|---:|---:|---:|---:|---:|",
        _distribution_row("All cases", overall),
        _distribution_row(
            "Most common variant",
            summarize_distribution(stats.loc[stats[IS_HAPPY_PATH], CYCLE_TIME]),
        ),
    ]
    others = stats.loc[~stats[IS_HAPPY_PATH], CYCLE_TIME]
    if len(others):
        rows.append(_distribution_row("All other variants", summarize_distribution(others)))

    if overall.p50 > 0 and overall.mean != overall.p50:
        direction = "above" if overall.mean > overall.p50 else "below"
        reason = (
            "pulled up by a minority of long-running cases"
            if overall.mean > overall.p50
            else "pulled down by a group of short cases"
        )
        gap = abs(overall.mean - overall.p50) / overall.p50
        skew = (
            f" The mean ({format_duration(overall.mean)}) is {gap:.0%} {direction} the median, "
            f"{reason}, so the median is the better figure for a typical case."
        )
    else:
        skew = ""
    narrative = (
        f"Half of all cases finish within {format_duration(overall.p50)}; one in ten takes longer "
        f"than {format_duration(overall.p90)}, and one in a hundred longer than "
        f"{format_duration(overall.p99)}.{skew}"
    )
    return "\n\n".join(["## Cycle time", "\n".join(rows), narrative])


def _process_map_section(inputs: DiscoveryInputs) -> str:
    """The Mermaid DFG with its coverage caption."""
    return "\n\n".join(
        [
            "## Process map (directly-follows graph)",
            inputs.diagram.caption,
            f"```mermaid\n{inputs.diagram.text.rstrip()}\n```",
            "Every edge with frequencies and durations: `dfg_edges.csv`.",
        ]
    )


def _model_section(inputs: DiscoveryInputs) -> str:
    """Mined-model shape and its loops, listed as leads for rework analysis."""
    net = inputs.net
    kinds = net.edges[KIND].value_counts()
    counts = ", ".join(
        f"{int(kinds.get(kind, 0))} {label}"
        for kind, label in (
            (CAUSAL, "causal"),
            (LENGTH_ONE_LOOP, "length-one loops"),
            (LENGTH_TWO_LOOP, "length-two-loop edges"),
            (BEST_CONNECTION, "best connections"),
        )
    )
    starts = ", ".join(f"`{a}` ({n:,})" for a, n in net.start_activities.items())
    lines = [
        "## Mined process model (heuristic miner)",
        f"Dependency threshold {net.threshold}: {len(net.edges)} edges ({counts}). "
        f"Start activities: {starts}. "
        f"Orphan activities: {', '.join(net.orphan_activities) or 'none'}.",
    ]

    loops = []
    self_loops = net.edges[net.edges[KIND] == LENGTH_ONE_LOOP]
    for edge in self_loops.itertuples(index=False):
        repeats = _plural(edge.frequency, "time", "times")
        loops.append(
            (
                edge.frequency,
                f"- `{edge.source}` repeats immediately: {repeats} "
                f"(length-one loop, measure {format_measure(edge.dependency)})",
            )
        )
    two_loops = net.edges[net.edges[KIND] == LENGTH_TWO_LOOP]
    for a, b in sorted({tuple(sorted((e.source, e.target))) for e in two_loops.itertuples()}):
        forward, backward = inputs.dfg.frequency(a, b), inputs.dfg.frequency(b, a)
        measure = float(
            two_loops[
                ((two_loops.source == a) & (two_loops.target == b))
                | ((two_loops.source == b) & (two_loops.target == a))
            ].dependency.iloc[0]
        )
        loops.append(
            (
                forward + backward,
                f"- `{a}` ⇄ `{b}`: {a} → {b} {forward:,}, {b} → {a} {backward:,} "
                f"(length-two loop, measure {format_measure(measure)})",
            )
        )
    if loops:
        lines.append("Loops found, the leads for rework analysis in Module B:")
        lines.append(
            "\n".join(text for _, text in sorted(loops, key=lambda item: (-item[0], item[1])))
        )
    lines.append("Full model: `heuristic_net.json`.")
    return "\n\n".join(lines)


def _caveats_section(inputs: DiscoveryInputs) -> str:
    """Conditions a reader needs before quoting any number above."""
    stats = inputs.case_stats
    outcomes = _outcomes(stats)
    caveats = []
    caveats.append(f"- {lifecycle_caveat(inputs.lifecycle)}")
    rank_one_mix = _outcome_mix(outcomes[stats[IS_HAPPY_PATH]])
    caveats.append(
        '- "Most common variant" is the requirements\' definition of the happy path. Its cases '
        f"end: {rank_one_mix}. Read it as the most frequent path, not necessarily a successful one."
    )
    open_cases = int((outcomes == NO_OUTCOME).sum())
    if open_cases:
        caveats.append(
            f"- {_plural(open_cases, 'case has', 'cases have')} no terminal state "
            f"({open_cases / len(stats):.1%}); their cycle times are lower bounds because they "
            "were still running when the log was extracted."
        )
    caveats.append("- Percentiles use linear interpolation between order statistics.")
    return "## Caveats\n\n" + "\n".join(caveats)
