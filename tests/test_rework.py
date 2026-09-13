"""Tests for rework detection and its cycle-time attribution, all derived by hand.

Cases (times in hours from each case's start):
- r1: A 0, B 1, C 2, B 5, C 6, D 8. B spans [1, 5], C spans [2, 6]: overlapping, union [1, 6] = 5 h.
- r2: A 0, B 1, B 1.5, D 3. B spans [1, 1.5] = 0.5 h.
- r3: A 0, B 1, D 2. No rework.
- r4: A 0, B 1, C 2, B 3, D 4, E 10, D 12. B [1, 3] and D [4, 12] are disjoint: 2 + 8 = 10 h.
Totals: rework 5 + 0.5 + 10 = 15.5 h; cycle 8 + 3 + 2 + 12 = 25 h; share 62%.
"""

import pandas as pd
import pytest
from test_dfg import LOG as DAY3_LOG

from meridian.config import get_settings
from meridian.conformance.rework import (
    ACTIVITY_REWORK_COLUMNS,
    CASE_REWORK_COLUMNS,
    analyze_rework,
)
from meridian.discovery.cycle_time import case_statistics
from meridian.discovery.variants import analyze_variants
from meridian.ingestion import schema
from meridian.ingestion.io import read_event_log_csv

HOUR = 3_600.0

CASES = {
    "r1": [("A", 0), ("B", 1), ("C", 2), ("B", 5), ("C", 6), ("D", 8)],
    "r2": [("A", 0), ("B", 1), ("B", 1.5), ("D", 3)],
    "r3": [("A", 0), ("B", 1), ("D", 2)],
    "r4": [("A", 0), ("B", 1), ("C", 2), ("B", 3), ("D", 4), ("E", 10), ("D", 12)],
}


def hours_log(cases: dict[str, list[tuple[str, float]]]) -> pd.DataFrame:
    """Build a normalized log from (activity, hours after the case's start) events."""
    start = pd.Timestamp("2016-01-01T00:00:00Z")
    rows = [
        (case_id, index, activity, start + pd.Timedelta(hours=hours), "u", None, None)
        for case_id, events in cases.items()
        for index, (activity, hours) in enumerate(events)
    ]
    return pd.DataFrame(rows, columns=list(schema.NORMALIZED_COLUMNS))


ANALYSIS = analyze_rework(hours_log(CASES))


def test_case_rework_counts_spans_and_shares() -> None:
    """Overlapping spans count once (r1); disjoint spans add up (r4); no repeats means zero (r3)."""
    cases = ANALYSIS.cases.set_index(schema.CASE_ID)

    assert tuple(ANALYSIS.cases.columns) == CASE_REWORK_COLUMNS
    assert cases.loc["r1", ["rework_events", "repeated_activities"]].tolist() == [2, 2]
    assert cases.loc["r1", "rework_seconds"] == pytest.approx(5 * HOUR)
    assert cases.loc["r1", "rework_share_of_cycle_time"] == pytest.approx(5 / 8)
    assert cases.loc["r2", "rework_seconds"] == pytest.approx(0.5 * HOUR)
    assert cases.loc["r3", ["rework_events", "rework_seconds"]].tolist() == [0, 0.0]
    assert cases.loc["r4", "rework_seconds"] == pytest.approx(10 * HOUR)


def test_dataset_totals_answer_how_much_time_rework_adds() -> None:
    """15.5 h of 25 h of cycle time sits inside rework loops; 3 of 4 cases have rework."""
    assert ANALYSIS.cases_with_rework == 3
    assert ANALYSIS.rework_case_share == pytest.approx(0.75)
    assert ANALYSIS.total_rework_seconds == pytest.approx(15.5 * HOUR)
    assert ANALYSIS.total_cycle_seconds == pytest.approx(25 * HOUR)
    assert ANALYSIS.rework_time_share == pytest.approx(0.62)


def test_distribution_covers_only_cases_with_rework() -> None:
    """Affected cases have 0.5, 5 and 10 hours of rework: median 5 h, mean 5.1667 h."""
    distribution = ANALYSIS.rework_time_distribution()

    assert distribution["p50"] == pytest.approx(5 * HOUR)
    assert distribution["mean"] == pytest.approx(15.5 / 3 * HOUR)


def test_activity_table_reports_repeats_and_spans() -> None:
    """B repeats in r1, r2 and r4 (spans 4 + 0.5 + 2 = 6.5 h); C and D once each."""
    activities = ANALYSIS.activities.set_index(schema.ACTIVITY)

    assert tuple(ANALYSIS.activities.columns) == ACTIVITY_REWORK_COLUMNS
    assert activities.loc["B", ["cases_with_rework", "repeat_occurrences"]].tolist() == [3, 3]
    assert activities.loc["B", "total_span_seconds"] == pytest.approx(6.5 * HOUR)
    assert activities.loc["D", "total_span_seconds"] == pytest.approx(8 * HOUR)
    assert list(ANALYSIS.activities[schema.ACTIVITY]) == ["D", "B", "C"]  # most span first


def test_three_executions_are_two_rework_events() -> None:
    """The first execution is the step itself; only repetitions count as rework."""
    analysis = analyze_rework(hours_log({"x": [("A", 0), ("B", 1), ("B", 2), ("B", 4), ("D", 5)]}))

    assert analysis.cases.loc[0, "rework_events"] == 2
    assert analysis.cases.loc[0, "rework_seconds"] == pytest.approx(3 * HOUR)
    assert analysis.activities.loc[0, "repeat_occurrences"] == 2


def test_log_without_rework_and_empty_log() -> None:
    """No repeats gives zero rework and an empty activity table; an empty log is rejected."""
    analysis = analyze_rework(hours_log({"r3": CASES["r3"]}))

    assert analysis.total_rework_seconds == 0.0
    assert analysis.activities.empty
    assert analysis.rework_time_distribution()["p50"] == 0.0
    with pytest.raises(ValueError, match="empty event log"):
        analyze_rework(hours_log({}).iloc[0:0])


def test_cycle_times_match_module_a() -> None:
    """Rework shares are fractions of the same cycle times Module A reports."""
    module_a = case_statistics(DAY3_LOG, analyze_variants(DAY3_LOG)).set_index(schema.CASE_ID)

    rework = analyze_rework(DAY3_LOG).cases.set_index(schema.CASE_ID)

    assert rework["cycle_time_seconds"].to_dict() == pytest.approx(
        module_a["cycle_time_seconds"].to_dict()
    )


@pytest.mark.integration
@pytest.mark.skipif(
    not get_settings().event_log_csv.exists(), reason="run `python -m meridian.discovery` first"
)
def test_real_log_rework_is_bounded_by_cycle_time() -> None:
    """On BPI 2017, no case's rework exceeds its cycle time, and totals reconcile with Module A."""
    log = read_event_log_csv(get_settings().event_log_csv)

    analysis = analyze_rework(log)

    assert len(analysis.cases) == log[schema.CASE_ID].nunique()
    assert (analysis.cases["rework_seconds"] <= analysis.cases["cycle_time_seconds"] + 1e-6).all()
    assert 0.0 <= analysis.rework_time_share <= 1.0
    module_a = case_statistics(log, analyze_variants(log))["cycle_time_seconds"].sum()
    assert analysis.total_cycle_seconds == pytest.approx(module_a, rel=1e-9)
