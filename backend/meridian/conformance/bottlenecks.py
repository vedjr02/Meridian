"""Bottleneck analysis: where time goes between steps, and whether the delay is uniform or erratic.

01-REQUIREMENTS.md Module B req. 3: for every transition, compute the distribution of wait time
rather than just the mean, and flag high-variance transitions separately from uniformly slow ones.
The two need different explanations and different fixes:
- **uniformly slow**: nearly every case waits a long time, which points at capacity, batching or
  policy, so the fix applies to the step for everyone;
- **high variance**: most cases pass quickly but some get stuck, which points at exceptions,
  missing information or prioritisation, so the fix starts from what the stuck cases share.

What "wait time" means here: the elapsed time between two consecutive recorded events of a case.
With one timestamp per event (the normalized schema, `complete` transitions for now), that span
includes the second activity's own processing as well as the queue before it. Separating the two
needs start events, which depends on the open lifecycle question (08-OPEN-QUESTIONS.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

from meridian.discovery.dfg import DURATION, SOURCE, TARGET, transition_occurrences
from meridian.ingestion import schema

# A transition needs this many occurrences before its spread is classified. Why 30: below that,
# quartiles move substantially when a single case changes, so a "high variance" flag would mostly
# reflect sample noise. Rarer transitions are still reported, just not classified.
MIN_OCCURRENCES = 30

# A transition is slow when its median wait is at or above this quantile of all transition medians
# in the log (each transition weighted once). Why relative to the log and why medians: an absolute
# threshold such as "one day" would encode an opinion about this business that the data does not
# support, and weighting each transition once stops the many near-instant automated steps from
# dragging the bar down to seconds.
SLOW_QUANTILE = 0.75

# Quartile coefficient of dispersion, (Q3 - Q1) / (Q3 + Q1), at or above which a transition counts
# as high variance. Why 0.5: it means the 75th-percentile wait is at least three times the
# 25th-percentile wait (Q3 = 3 * Q1 gives exactly 0.5), a spread large enough that "the typical
# case" no longer describes the transition. A moderate doubling (Q3 = 2 * Q1) scores 0.33.
DISPERSION_THRESHOLD = 0.5

OCCURRENCES = "occurrences"
CASES = "cases"
TOTAL_SECONDS = "total_seconds"
SHARE_OF_TOTAL = "share_of_total_time"
MEAN_SECONDS = "mean_seconds"
Q1_SECONDS = "q1_seconds"
P50_SECONDS = "p50_seconds"
Q3_SECONDS = "q3_seconds"
P90_SECONDS = "p90_seconds"
P99_SECONDS = "p99_seconds"
MAX_SECONDS = "max_seconds"
DISPERSION = "dispersion"
KIND = "kind"
BOTTLENECK_COLUMNS = (
    SOURCE,
    TARGET,
    OCCURRENCES,
    CASES,
    TOTAL_SECONDS,
    SHARE_OF_TOTAL,
    MEAN_SECONDS,
    Q1_SECONDS,
    P50_SECONDS,
    Q3_SECONDS,
    P90_SECONDS,
    P99_SECONDS,
    MAX_SECONDS,
    DISPERSION,
    KIND,
)


class BottleneckKind(StrEnum):
    """How a transition's wait-time distribution is classified."""

    UNIFORMLY_SLOW = "uniformly_slow"
    HIGH_VARIANCE = "high_variance"
    SLOW_AND_VARIABLE = "slow_and_variable"
    NOT_FLAGGED = "not_flagged"
    INSUFFICIENT_DATA = "insufficient_data"


def quartile_dispersion(q1: float, q3: float) -> float:
    """Quartile coefficient of dispersion, (Q3 - Q1) / (Q3 + Q1), in [0, 1].

    Why this measure rather than the standard deviation or coefficient of variation: wait times are
    heavy-tailed, and a handful of extreme cases would dominate any moment-based measure. Quartiles
    ignore the extremes (reported separately as p99 and max), and the ratio is unit-free, so a
    minutes-long step and a weeks-long step are compared fairly. Defined as 0 when both quartiles
    are 0: a transition that is instantaneous for at least three quarters of cases has no spread
    worth flagging at the quartiles.
    """
    if q1 < 0 or q3 < q1:
        raise ValueError(f"Quartiles must satisfy 0 <= Q1 <= Q3, got {q1}, {q3}")
    if q1 + q3 == 0:
        return 0.0
    return (q3 - q1) / (q3 + q1)


def classify_transition(
    occurrences: int,
    median_seconds: float,
    dispersion: float,
    *,
    slow_threshold_seconds: float,
    dispersion_threshold: float = DISPERSION_THRESHOLD,
    min_occurrences: int = MIN_OCCURRENCES,
) -> BottleneckKind:
    """Classify one transition from its size, typical wait and spread.

    Slowness uses the median (the typical case) and variance uses quartile dispersion, so the two
    flags answer independent questions and a transition can raise both.
    """
    if occurrences < min_occurrences:
        return BottleneckKind.INSUFFICIENT_DATA
    slow = median_seconds >= slow_threshold_seconds and median_seconds > 0
    variable = dispersion >= dispersion_threshold
    if slow and variable:
        return BottleneckKind.SLOW_AND_VARIABLE
    if slow:
        return BottleneckKind.UNIFORMLY_SLOW
    if variable:
        return BottleneckKind.HIGH_VARIANCE
    return BottleneckKind.NOT_FLAGGED


@dataclass(frozen=True)
class BottleneckAnalysis:
    """Wait-time distribution and classification for every transition in a log.

    Attributes:
        transitions: Columns `BOTTLENECK_COLUMNS`, most total time first.
        slow_threshold_seconds: The median wait at or above which a transition counted as slow.
        dispersion_threshold: The quartile dispersion at or above which it counted as variable.
        min_occurrences: Occurrences needed before a transition is classified.
        total_seconds: Elapsed time summed over every transition occurrence in the log.
    """

    transitions: pd.DataFrame
    slow_threshold_seconds: float
    dispersion_threshold: float
    min_occurrences: int
    total_seconds: float

    def most_costly(self) -> pd.Series:
        """The single transition with the most aggregate elapsed time (Module B acceptance)."""
        return self.transitions.iloc[0]

    def flagged(self, kind: BottleneckKind) -> pd.DataFrame:
        """Transitions of one kind, most total time first."""
        return self.transitions[self.transitions[KIND] == kind.value]


def analyze_bottlenecks(
    event_log: pd.DataFrame,
    *,
    min_occurrences: int = MIN_OCCURRENCES,
    slow_quantile: float = SLOW_QUANTILE,
    dispersion_threshold: float = DISPERSION_THRESHOLD,
    slow_threshold_seconds: float | None = None,
) -> BottleneckAnalysis:
    """Compute each transition's wait-time distribution, aggregate cost and bottleneck kind.

    Args:
        event_log: Normalized event log.
        min_occurrences: Occurrences needed before a transition is classified.
        slow_quantile: Quantile of transition medians that defines "slow" when no explicit
            threshold is given. Only transitions with enough occurrences contribute, so rare
            transitions cannot move the bar.
        dispersion_threshold: Quartile dispersion that defines "high variance".
        slow_threshold_seconds: Explicit slow threshold, overriding `slow_quantile`.

    Percentiles use linear interpolation, as everywhere else in the project.
    """
    if not 0 < slow_quantile < 1:
        raise ValueError(f"slow_quantile must be strictly between 0 and 1, got {slow_quantile}")
    occurrences = transition_occurrences(event_log)
    if occurrences.empty:
        raise ValueError("The event log has no transitions to analyse")

    rows = []
    for (source, target), group in occurrences.groupby([SOURCE, TARGET], sort=True):
        durations = group[DURATION].to_numpy(dtype=float)
        q1, p50, q3, p90, p99 = np.percentile(durations, [25, 50, 75, 90, 99])
        rows.append(
            {
                SOURCE: source,
                TARGET: target,
                OCCURRENCES: len(durations),
                CASES: group[schema.CASE_ID].nunique(),
                TOTAL_SECONDS: float(durations.sum()),
                MEAN_SECONDS: float(durations.mean()),
                Q1_SECONDS: float(q1),
                P50_SECONDS: float(p50),
                Q3_SECONDS: float(q3),
                P90_SECONDS: float(p90),
                P99_SECONDS: float(p99),
                MAX_SECONDS: float(durations.max()),
                DISPERSION: quartile_dispersion(float(q1), float(q3)),
            }
        )
    table = pd.DataFrame(rows)

    if slow_threshold_seconds is None:
        eligible = table.loc[table[OCCURRENCES] >= min_occurrences, P50_SECONDS]
        source_values = eligible if len(eligible) else table[P50_SECONDS]
        slow_threshold_seconds = float(np.quantile(source_values.to_numpy(), slow_quantile))

    total = float(table[TOTAL_SECONDS].sum())
    table[SHARE_OF_TOTAL] = table[TOTAL_SECONDS] / total if total else 0.0
    table[KIND] = [
        classify_transition(
            int(row[OCCURRENCES]),
            float(row[P50_SECONDS]),
            float(row[DISPERSION]),
            slow_threshold_seconds=slow_threshold_seconds,
            dispersion_threshold=dispersion_threshold,
            min_occurrences=min_occurrences,
        ).value
        for _, row in table.iterrows()
    ]
    table = table.sort_values(
        [TOTAL_SECONDS, SOURCE, TARGET], ascending=[False, True, True], kind="stable"
    ).reset_index(drop=True)
    return BottleneckAnalysis(
        transitions=table.loc[:, list(BOTTLENECK_COLUMNS)],
        slow_threshold_seconds=slow_threshold_seconds,
        dispersion_threshold=dispersion_threshold,
        min_occurrences=min_occurrences,
        total_seconds=total,
    )
