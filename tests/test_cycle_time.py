"""Tests for per-case statistics and the cycle-time distribution summary."""

import pandas as pd
import pytest
from test_dfg import LOG as DAY3_LOG

from meridian.discovery.cycle_time import (
    ACTIVITY_COUNT,
    CASE_STATISTICS_COLUMNS,
    CYCLE_TIME,
    IS_HAPPY_PATH,
    case_statistics,
    summarize_distribution,
)
from meridian.discovery.variants import VARIANT_RANK, analyze_variants
from meridian.ingestion import schema


def test_percentiles_match_hand_computed_linear_interpolation() -> None:
    """For 1..100: p50 = 50.5, p90 = 90.1, p99 = 99.01 under linear interpolation."""
    summary = summarize_distribution(pd.Series(range(1, 101), dtype="float64"))

    assert summary.count == 100
    assert summary.mean == pytest.approx(50.5)
    assert (summary.p50, summary.p90, summary.p99) == pytest.approx((50.5, 90.1, 99.01))
    assert (summary.minimum, summary.maximum) == (1.0, 100.0)


def test_skewed_distribution_shows_mean_far_from_median() -> None:
    """Nine 1-day cases and one 91-day case: median 1 day, mean 10 days. Why percentiles matter."""
    day = 86_400.0
    summary = summarize_distribution(pd.Series([day] * 9 + [91 * day]))

    assert summary.p50 == day
    assert summary.mean == pytest.approx(10 * day)
    assert summary.p99 > 80 * day


def test_empty_distribution_is_rejected() -> None:
    """A summary of nothing would print plausible-looking zeros; it must fail instead."""
    with pytest.raises(ValueError):
        summarize_distribution(pd.Series([], dtype="float64"))


def test_case_statistics_on_day3_log() -> None:
    """Hand-checked: c1 09:00-13:00 is 4 h over 4 events; c5 is a single event (0 s)."""
    variants = analyze_variants(DAY3_LOG)

    stats = case_statistics(DAY3_LOG, variants).set_index(schema.CASE_ID)

    assert tuple(stats.reset_index().columns) == CASE_STATISTICS_COLUMNS
    assert stats.loc["c1", CYCLE_TIME] == 4 * 3600
    assert stats.loc["c1", ACTIVITY_COUNT] == 4
    assert stats.loc["c3", CYCLE_TIME] == 3 * 3600 + 45 * 60  # 08:00-11:45
    assert stats.loc["c5", CYCLE_TIME] == 0
    assert stats[ACTIVITY_COUNT].sum() == len(DAY3_LOG)


def test_happy_path_flags_exactly_the_most_frequent_variant() -> None:
    """Happy path = the rank-1 variant (01-REQUIREMENTS Module A req. 4)."""
    rows = []
    for case_number, activities in enumerate(["ABC", "ABC", "ABC", "ACB", "AB"]):
        for index, activity in enumerate(activities):
            timestamp = pd.Timestamp("2016-01-01T09:00Z") + pd.Timedelta(hours=index)
            rows.append((f"k{case_number}", index, activity, timestamp, "u", None, "done"))
    log = pd.DataFrame(rows, columns=list(schema.NORMALIZED_COLUMNS))

    stats = case_statistics(log, analyze_variants(log))

    assert stats[IS_HAPPY_PATH].tolist() == [True, True, True, False, False]
    # Single-case variants tie; "A > B" sorts before "A > C > B", so k4 is rank 2 and k3 rank 3.
    assert stats[VARIANT_RANK].tolist() == [1, 1, 1, 3, 2]
    assert stats[schema.OUTCOME].tolist() == ["done"] * 5
