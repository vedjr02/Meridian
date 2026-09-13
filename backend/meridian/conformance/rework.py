"""Rework detection: activities a case performs more than once, and the cycle time that costs.

01-REQUIREMENTS.md Module B req. 4: identify cases where the same activity recurs within one case,
and quantify the total added cycle time attributable to rework across the dataset.

How time is attributed, stated explicitly because any rework cost figure depends on it:
- An activity performed more than once in a case has a **rework span**: from its first occurrence to
  its last. Everything in between happened because the case came back to that activity; a case that
  got it right the first time would have moved on after the first occurrence.
- A case's **rework time** is the union of its rework spans. Spans of different activities often
  overlap (a validate and incomplete loop repeats both), and adding them would count the same hours
  twice.

This is an attribution rule, not a counterfactual estimate. It does not claim the case would have
finished exactly that much sooner, since some of the looped time might have been spent waiting
anyway; it answers "how much of the recorded cycle time sits inside rework loops".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from meridian.ingestion import schema

REWORK_EVENTS = "rework_events"
REPEATED_ACTIVITIES = "repeated_activities"
REWORK_SECONDS = "rework_seconds"
CYCLE_TIME_SECONDS = "cycle_time_seconds"
REWORK_SHARE = "rework_share_of_cycle_time"
CASE_REWORK_COLUMNS = (
    schema.CASE_ID,
    REWORK_EVENTS,
    REPEATED_ACTIVITIES,
    REWORK_SECONDS,
    CYCLE_TIME_SECONDS,
    REWORK_SHARE,
)

CASES_WITH_REWORK = "cases_with_rework"
REPEAT_OCCURRENCES = "repeat_occurrences"
TOTAL_SPAN_SECONDS = "total_span_seconds"
MEDIAN_SPAN_SECONDS = "median_span_seconds"
ACTIVITY_REWORK_COLUMNS = (
    schema.ACTIVITY,
    CASES_WITH_REWORK,
    REPEAT_OCCURRENCES,
    TOTAL_SPAN_SECONDS,
    MEDIAN_SPAN_SECONDS,
)

_START = "first_seconds"
_END = "last_seconds"
_COUNT = "occurrences"


@dataclass(frozen=True)
class ReworkAnalysis:
    """Rework per case and per activity, with dataset-level totals.

    Attributes:
        cases: Every case, columns `CASE_REWORK_COLUMNS`, ordered by case id. Cases without rework
            have zero rework events and zero rework time.
        activities: Each activity that is ever repeated, columns `ACTIVITY_REWORK_COLUMNS`, most
            total span first. Spans overlap across activities, so this table's totals are not
            additive; `total_rework_seconds` is.
    """

    cases: pd.DataFrame
    activities: pd.DataFrame

    @property
    def cases_with_rework(self) -> int:
        """Number of cases that perform at least one activity more than once."""
        return int((self.cases[REWORK_EVENTS] > 0).sum())

    @property
    def rework_case_share(self) -> float:
        """Share of all cases that contain rework."""
        return self.cases_with_rework / len(self.cases)

    @property
    def total_rework_seconds(self) -> float:
        """Cycle time inside rework loops, summed over cases: the "time rework adds" headline."""
        return float(self.cases[REWORK_SECONDS].sum())

    @property
    def total_cycle_seconds(self) -> float:
        """Cycle time summed over every case, the denominator for the rework share."""
        return float(self.cases[CYCLE_TIME_SECONDS].sum())

    @property
    def rework_time_share(self) -> float:
        """Share of all recorded cycle time that sits inside rework loops."""
        total = self.total_cycle_seconds
        return self.total_rework_seconds / total if total else 0.0

    def rework_time_distribution(self) -> dict[str, float]:
        """Rework time per affected case: p50, p90, p99 and mean, in seconds (linear interpolation).

        Why only cases with rework: including the cases without any would put the median at zero
        whenever fewer than half the cases loop, which says nothing about how costly a loop is.
        """
        values = self.cases.loc[self.cases[REWORK_EVENTS] > 0, REWORK_SECONDS].to_numpy(float)
        if values.size == 0:
            return {"p50": 0.0, "p90": 0.0, "p99": 0.0, "mean": 0.0}
        p50, p90, p99 = np.percentile(values, [50, 90, 99])
        return {
            "p50": float(p50),
            "p90": float(p90),
            "p99": float(p99),
            "mean": float(values.mean()),
        }


def _union_length(spans: pd.DataFrame) -> pd.Series:
    """Total length covered by each case's spans, counting overlapping stretches once.

    Spans are sorted by start within each case; each span then contributes only the part that
    ends after everything before it, `max(0, end - max(start, latest end so far))`. This is the
    standard interval-union sweep, done with grouped cumulative maxima instead of a Python loop.
    """
    ordered = spans.sort_values([schema.CASE_ID, _START, _END], kind="stable")
    previous_end = ordered.groupby(schema.CASE_ID, sort=False)[_END].cummax()
    previous_end = previous_end.groupby(ordered[schema.CASE_ID], sort=False).shift()
    effective_start = np.maximum(
        ordered[_START].to_numpy(), previous_end.fillna(-np.inf).to_numpy()
    )
    contribution = np.clip(ordered[_END].to_numpy() - effective_start, 0, None)
    return pd.Series(contribution, index=ordered.index).groupby(ordered[schema.CASE_ID]).sum()


def analyze_rework(event_log: pd.DataFrame) -> ReworkAnalysis:
    """Detect repeated activities in every case and attribute cycle time to rework.

    Why repeats are counted per activity occurrence beyond the first: three executions of a step are
    two rework events. The first execution is the step itself, and only the repetitions are rework.
    """
    if event_log.empty:
        raise ValueError("Cannot analyse rework in an empty event log")
    seconds = (event_log[schema.TIMESTAMP] - event_log[schema.TIMESTAMP].min()).dt.total_seconds()
    log = pd.DataFrame(
        {
            schema.CASE_ID: event_log[schema.CASE_ID].to_numpy(),
            schema.ACTIVITY: event_log[schema.ACTIVITY].to_numpy(),
            "seconds": seconds.to_numpy(),
        }
    )

    per_activity = (
        log.groupby([schema.CASE_ID, schema.ACTIVITY], sort=True)["seconds"]
        .agg(**{_COUNT: "size", _START: "min", _END: "max"})
        .reset_index()
    )
    repeated = per_activity[per_activity[_COUNT] > 1].copy()
    repeated["span"] = repeated[_END] - repeated[_START]

    bounds = log.groupby(schema.CASE_ID, sort=True)["seconds"].agg(["min", "max"])
    cases = pd.DataFrame(
        {
            schema.CASE_ID: bounds.index,
            CYCLE_TIME_SECONDS: (bounds["max"] - bounds["min"]).to_numpy(),
        }
    )
    if repeated.empty:
        cases[REWORK_EVENTS] = 0
        cases[REPEATED_ACTIVITIES] = 0
        cases[REWORK_SECONDS] = 0.0
    else:
        by_case = repeated.groupby(schema.CASE_ID)
        cases[REWORK_EVENTS] = (
            cases[schema.CASE_ID].map(by_case[_COUNT].sum() - by_case.size()).fillna(0).astype(int)
        )
        cases[REPEATED_ACTIVITIES] = cases[schema.CASE_ID].map(by_case.size()).fillna(0).astype(int)
        cases[REWORK_SECONDS] = cases[schema.CASE_ID].map(_union_length(repeated)).fillna(0.0)
    cycle_seconds = cases[CYCLE_TIME_SECONDS].to_numpy(float)
    cases[REWORK_SHARE] = np.divide(
        cases[REWORK_SECONDS].to_numpy(float),
        cycle_seconds,
        out=np.zeros_like(cycle_seconds),
        where=cycle_seconds > 0,
    )

    activities = (
        repeated.groupby(schema.ACTIVITY, sort=True)
        .agg(
            **{
                CASES_WITH_REWORK: (schema.CASE_ID, "nunique"),
                REPEAT_OCCURRENCES: (_COUNT, lambda counts: int((counts - 1).sum())),
                TOTAL_SPAN_SECONDS: ("span", "sum"),
                MEDIAN_SPAN_SECONDS: ("span", "median"),
            }
        )
        .reset_index()
        .sort_values([TOTAL_SPAN_SECONDS, schema.ACTIVITY], ascending=[False, True], kind="stable")
        .reset_index(drop=True)
        if not repeated.empty
        else pd.DataFrame(columns=list(ACTIVITY_REWORK_COLUMNS))
    )
    return ReworkAnalysis(
        cases=cases.loc[:, list(CASE_REWORK_COLUMNS)],
        activities=activities.loc[:, list(ACTIVITY_REWORK_COLUMNS)],
    )
