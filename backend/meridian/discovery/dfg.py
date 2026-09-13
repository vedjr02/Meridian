"""Directly-follows graph (DFG): which activity directly follows which, how often, and how long.

The DFG is the first structural view of the process and the input to the heuristic miner: its
edge frequencies are exactly the |A>B| counts that the dependency measure is computed from.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import pandas as pd

from meridian.ingestion import schema

SOURCE = "source"
TARGET = "target"
FREQUENCY = "frequency"
CASE_FREQUENCY = "case_frequency"
MEAN_DURATION = "mean_duration_seconds"
MEDIAN_DURATION = "median_duration_seconds"
EDGE_COLUMNS = (SOURCE, TARGET, FREQUENCY, CASE_FREQUENCY, MEAN_DURATION, MEDIAN_DURATION)

REQUIRED_COLUMNS = (schema.CASE_ID, schema.EVENT_INDEX, schema.ACTIVITY, schema.TIMESTAMP)

_DURATION = "duration_seconds"


@dataclass(frozen=True)
class DirectlyFollowsGraph:
    """Aggregated directly-follows relations of an event log.

    Attributes:
        edges: One row per observed (source, target) pair, columns `EDGE_COLUMNS`, most frequent
            first. `frequency` counts every occurrence; `case_frequency` counts distinct cases, so
            a pair repeated inside one rework loop is visible as frequency > case_frequency.
        start_activities: Number of cases that begin with each activity.
        end_activities: Number of cases that end with each activity.
        activity_counts: Number of events carrying each activity.
        case_count: Number of cases in the log.
    """

    edges: pd.DataFrame
    start_activities: dict[str, int]
    end_activities: dict[str, int]
    activity_counts: dict[str, int]
    case_count: int

    @property
    def transition_count(self) -> int:
        """Total directly-follows occurrences; for any log this equals events minus cases."""
        return int(self.edges[FREQUENCY].sum())

    @cached_property
    def _frequencies(self) -> dict[tuple[str, str], int]:
        """Pair-to-frequency index, built once so pairwise lookups are constant time."""
        return {
            (source, target): int(count)
            for source, target, count in self.edges[[SOURCE, TARGET, FREQUENCY]].itertuples(
                index=False, name=None
            )
        }

    def frequency(self, source: str, target: str) -> int:
        """Return |source > target|, how often `target` directly follows `source` (0 if never).

        Why a lookup method: the heuristic miner reads these counts pairwise and in both
        directions, and a pair that never occurs must count as zero rather than raise.
        """
        return self._frequencies.get((source, target), 0)


def _sorted_counts(values: pd.Series) -> dict[str, int]:
    """Count values, most frequent first with ties alphabetical, as a plain dict.

    Why a fixed tie order: outputs written to files and reports must be identical across runs,
    and `value_counts` alone does not guarantee an order among equal counts.
    """
    counts = values.value_counts()
    ordered = sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))
    return {str(value): int(count) for value, count in ordered}


def build_dfg(event_log: pd.DataFrame) -> DirectlyFollowsGraph:
    """Compute the directly-follows graph of a normalized event log.

    Why order by (case_id, event_index) and never by timestamp: events can share a timestamp, and
    the source file's order is the only reliable tiebreak. Sorting by time would make edges depend
    on how a sort algorithm happens to break ties, and the same log could yield different graphs.

    Why a transition's duration is the gap between the two events' timestamps: with one timestamp
    per event (the normalized schema), that gap is the only duration the log supports. For a
    `complete`-only log it is the second activity's waiting plus processing time; separating those
    two is Module B's job.

    Why the median is reported beside the mean: event-log durations are heavily right-skewed, so a
    mean alone misrepresents a typical transition (03-UIUX-RULES.md rule 1). Full distributions
    belong to Module B's bottleneck analysis.
    """
    missing = [column for column in REQUIRED_COLUMNS if column not in event_log.columns]
    if missing:
        raise ValueError(f"Event log is missing required columns: {missing}")

    log = (
        event_log.loc[:, list(REQUIRED_COLUMNS)]
        .sort_values([schema.CASE_ID, schema.EVENT_INDEX], kind="stable")
        .reset_index(drop=True)
    )
    following = log.shift(-1)
    same_case = (
        log[schema.CASE_ID].eq(following[schema.CASE_ID]).to_numpy(dtype=bool, na_value=False)
    )

    transitions = pd.DataFrame(
        {
            SOURCE: log.loc[same_case, schema.ACTIVITY].to_numpy(),
            TARGET: following.loc[same_case, schema.ACTIVITY].to_numpy(),
            schema.CASE_ID: log.loc[same_case, schema.CASE_ID].to_numpy(),
            _DURATION: (
                following.loc[same_case, schema.TIMESTAMP] - log.loc[same_case, schema.TIMESTAMP]
            )
            .dt.total_seconds()
            .to_numpy(),
        }
    )

    by_case = log.groupby(schema.CASE_ID, sort=False)[schema.ACTIVITY]
    return DirectlyFollowsGraph(
        edges=_aggregate_edges(transitions),
        start_activities=_sorted_counts(by_case.first()),
        end_activities=_sorted_counts(by_case.last()),
        activity_counts=_sorted_counts(log[schema.ACTIVITY]),
        case_count=int(log[schema.CASE_ID].nunique()),
    )


def _aggregate_edges(transitions: pd.DataFrame) -> pd.DataFrame:
    """Collapse individual transitions into one row per (source, target) pair.

    Why an explicit empty result: a log whose cases all have a single event has no transitions,
    and downstream code should still receive the documented columns and dtypes, not a shapeless
    frame from aggregating nothing.
    """
    if transitions.empty:
        return pd.DataFrame(
            {
                SOURCE: pd.Series(dtype="string"),
                TARGET: pd.Series(dtype="string"),
                FREQUENCY: pd.Series(dtype="int64"),
                CASE_FREQUENCY: pd.Series(dtype="int64"),
                MEAN_DURATION: pd.Series(dtype="float64"),
                MEDIAN_DURATION: pd.Series(dtype="float64"),
            }
        )
    edges = (
        transitions.groupby([SOURCE, TARGET], sort=False)
        .agg(
            **{
                FREQUENCY: (schema.CASE_ID, "size"),
                CASE_FREQUENCY: (schema.CASE_ID, "nunique"),
                MEAN_DURATION: (_DURATION, "mean"),
                MEDIAN_DURATION: (_DURATION, "median"),
            }
        )
        .reset_index()
    )
    return edges.sort_values(
        [FREQUENCY, SOURCE, TARGET], ascending=[False, True, True], kind="stable"
    ).reset_index(drop=True)[list(EDGE_COLUMNS)]
