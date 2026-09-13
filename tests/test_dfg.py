"""Tests for the directly-follows graph against a hand-crafted log with known answers.

Every expected value below was computed by hand from `LOG`, so these tests verify correctness,
not merely that the code runs.
"""

import pandas as pd
import pytest

from meridian.discovery.dfg import (
    CASE_FREQUENCY,
    EDGE_COLUMNS,
    FREQUENCY,
    MEAN_DURATION,
    MEDIAN_DURATION,
    SOURCE,
    TARGET,
    build_dfg,
)
from meridian.ingestion import schema

# (case, activity, time) — event_index is the position within the case as listed.
TRACES = {
    "c1": [("A", "09:00"), ("B", "10:00"), ("C", "12:00"), ("D", "13:00")],
    "c2": [("A", "09:00"), ("C", "09:30"), ("B", "11:30"), ("D", "12:30")],
    "c3": [("A", "08:00"), ("B", "08:15"), ("B", "08:45"), ("C", "10:45"), ("D", "11:45")],
    "c4": [("X", "07:00"), ("D", "07:30")],
    "c5": [("A", "06:00")],
    "c6": [("A", "06:00"), ("B", "06:10"), ("A", "06:20"), ("B", "06:50"), ("D", "07:00")],
}


def make_log(traces: dict[str, list[tuple[str, str]]], day: str = "2016-01-01") -> pd.DataFrame:
    """Build a normalized-schema log from compact (activity, HH:MM) traces."""
    rows = [
        (case_id, index, activity, pd.Timestamp(f"{day}T{time}:00Z"), "User_1", None, None)
        for case_id, events in traces.items()
        for index, (activity, time) in enumerate(events)
    ]
    return pd.DataFrame(rows, columns=list(schema.NORMALIZED_COLUMNS))


LOG = make_log(TRACES)

# Hand-computed: (frequency, case_frequency, mean seconds, median seconds) per edge.
EXPECTED_EDGES = {
    ("A", "B"): (4, 3, 1725.0, 1350.0),  # c1 3600, c3 900, c6 600 + 1800
    ("B", "C"): (2, 2, 7200.0, 7200.0),  # c1, c3
    ("C", "D"): (2, 2, 3600.0, 3600.0),  # c1, c3
    ("B", "D"): (2, 2, 2100.0, 2100.0),  # c2 3600, c6 600
    ("A", "C"): (1, 1, 1800.0, 1800.0),  # c2
    ("C", "B"): (1, 1, 7200.0, 7200.0),  # c2
    ("B", "B"): (1, 1, 1800.0, 1800.0),  # c3 self-loop
    ("X", "D"): (1, 1, 1800.0, 1800.0),  # c4
    ("B", "A"): (1, 1, 600.0, 600.0),  # c6
}


def _edge_table(dfg) -> dict[tuple[str, str], tuple]:
    """Index a DFG's edges by (source, target) for exact comparison."""
    return {
        (row[SOURCE], row[TARGET]): (
            row[FREQUENCY],
            row[CASE_FREQUENCY],
            row[MEAN_DURATION],
            row[MEDIAN_DURATION],
        )
        for _, row in dfg.edges.iterrows()
    }


def test_edges_match_hand_computed_frequencies_and_durations() -> None:
    """Frequency, case frequency, mean and median for every edge, including a self-loop."""
    dfg = build_dfg(LOG)

    assert tuple(dfg.edges.columns) == EDGE_COLUMNS
    assert _edge_table(dfg) == EXPECTED_EDGES


def test_frequency_exceeds_case_frequency_when_a_pair_repeats_within_a_case() -> None:
    """c6 performs A->B twice; rework must be visible as frequency 4 against 3 cases."""
    edge = build_dfg(LOG).edges.query("source == 'A' and target == 'B'").iloc[0]

    assert (edge[FREQUENCY], edge[CASE_FREQUENCY]) == (4, 3)


def test_start_end_and_activity_counts() -> None:
    """Start/end activities feed the mined model; a single-event case both starts and ends it."""
    dfg = build_dfg(LOG)

    assert dfg.start_activities == {"A": 5, "X": 1}
    assert dfg.end_activities == {"D": 5, "A": 1}
    assert dfg.activity_counts == {"A": 6, "B": 6, "D": 5, "C": 3, "X": 1}
    assert dfg.case_count == 6


def test_transition_count_equals_events_minus_cases() -> None:
    """A case of n events has exactly n-1 transitions; anything else means lost or extra edges."""
    dfg = build_dfg(LOG)

    assert dfg.transition_count == len(LOG) - LOG[schema.CASE_ID].nunique() == 15


def test_frequency_lookup_returns_zero_for_unseen_pairs() -> None:
    """The heuristic miner reads |A>B| and |B>A|; a pair that never occurs must read as 0."""
    dfg = build_dfg(LOG)

    assert dfg.frequency("A", "B") == 4
    assert dfg.frequency("B", "A") == 1
    assert dfg.frequency("D", "A") == 0


def test_result_does_not_depend_on_input_row_order() -> None:
    """Shuffled rows must give the same graph, since order comes from case and event_index."""
    shuffled = LOG.sample(frac=1.0, random_state=7).reset_index(drop=True)

    assert _edge_table(build_dfg(shuffled)) == EXPECTED_EDGES


def test_event_index_breaks_timestamp_ties() -> None:
    """With identical timestamps, the source order (P before Q) must decide the edge direction."""
    tied = make_log({"t1": [("P", "09:00"), ("Q", "09:00")]})

    dfg = build_dfg(tied.iloc[::-1].reset_index(drop=True))

    assert dfg.frequency("P", "Q") == 1
    assert dfg.frequency("Q", "P") == 0


def test_log_without_transitions_returns_empty_edges_with_schema() -> None:
    """Single-event cases produce no edges, but callers still get the documented columns."""
    dfg = build_dfg(make_log({"s1": [("A", "09:00")], "s2": [("B", "10:00")]}))

    assert dfg.edges.empty
    assert tuple(dfg.edges.columns) == EDGE_COLUMNS
    assert dfg.transition_count == 0
    assert dfg.start_activities == {"A": 1, "B": 1}


def test_missing_required_column_is_rejected() -> None:
    """A malformed input must fail loudly rather than produce a plausible-looking empty graph."""
    with pytest.raises(ValueError, match="event_index"):
        build_dfg(LOG.drop(columns=[schema.EVENT_INDEX]))
