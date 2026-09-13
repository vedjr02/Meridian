"""Tests for bottleneck analysis: distributions, dispersion, classification and aggregate cost.

`SPEC` builds one two-event case per listed duration, so each transition's occurrences are exactly
the durations given. Quartiles below use linear interpolation over 40 sorted values:
Q1 at position 9.75, median at 19.5, Q3 at 29.25.
"""

import pandas as pd
import pytest
from test_dfg import LOG as DAY3_LOG

from meridian.config import get_settings
from meridian.conformance.bottlenecks import (
    BOTTLENECK_COLUMNS,
    BottleneckKind,
    analyze_bottlenecks,
    classify_transition,
    quartile_dispersion,
)
from meridian.discovery.cycle_time import case_statistics
from meridian.discovery.variants import analyze_variants
from meridian.ingestion import schema
from meridian.ingestion.io import read_event_log_csv

HOUR = 3_600.0
DAY = 86_400.0

SPEC = [
    ("A", "B", [10 * DAY] * 40),  # uniformly slow: every case waits 10 days
    ("B", "C", [HOUR] * 20 + [10 * DAY] * 20),  # erratic: Q1 1 h, Q3 10 d, median 120.5 h
    ("C", "D", [HOUR] * 40),  # fast and uniform
    ("D", "E", [2 * HOUR] * 5),  # too rare to classify
    ("E", "F", [9 * DAY] * 20 + [30 * DAY] * 20),  # slow and erratic: Q1 9 d, Q3 30 d
]


def pair_log(spec: list[tuple[str, str, list[float]]]) -> pd.DataFrame:
    """One case per duration: `source` at a fixed time, then `target` that many seconds later."""
    rows, number = [], 0
    start = pd.Timestamp("2016-01-01T00:00:00Z")
    for source, target, durations in spec:
        for seconds in durations:
            number += 1
            case = f"case{number:03d}"
            rows.append((case, 0, source, start, "u", None, None))
            rows.append((case, 1, target, start + pd.Timedelta(seconds=seconds), "u", None, None))
    return pd.DataFrame(rows, columns=list(schema.NORMALIZED_COLUMNS))


LOG = pair_log(SPEC)


@pytest.mark.parametrize(
    ("q1", "q3", "expected"),
    [(HOUR, 10 * DAY, 239 / 241), (9 * DAY, 30 * DAY, 21 / 39), (5.0, 5.0, 0.0), (0.0, 0.0, 0.0)],
)
def test_quartile_dispersion(q1: float, q3: float, expected: float) -> None:
    """(Q3 - Q1) / (Q3 + Q1); Q3 = 3 * Q1 would score exactly 0.5; all-zero quartiles score 0."""
    assert quartile_dispersion(q1, q3) == pytest.approx(expected)
    assert quartile_dispersion(10.0, 30.0) == 0.5


def test_dispersion_rejects_impossible_quartiles() -> None:
    """Q3 below Q1, or negative waits, can only come from a bug upstream."""
    with pytest.raises(ValueError):
        quartile_dispersion(5.0, 1.0)


@pytest.mark.parametrize(
    ("occurrences", "median", "dispersion", "kind"),
    [
        (40, 10 * DAY, 0.0, BottleneckKind.UNIFORMLY_SLOW),
        (40, 5 * DAY, 0.99, BottleneckKind.HIGH_VARIANCE),
        (40, 19.5 * DAY, 0.54, BottleneckKind.SLOW_AND_VARIABLE),
        (40, HOUR, 0.0, BottleneckKind.NOT_FLAGGED),
        (29, 10 * DAY, 0.9, BottleneckKind.INSUFFICIENT_DATA),
        (40, 0.0, 0.0, BottleneckKind.NOT_FLAGGED),
    ],
)
def test_classification_rules(occurrences, median, dispersion, kind) -> None:
    """Slow is median at or above the threshold (6 days here); variable is dispersion >= 0.5."""
    assert (
        classify_transition(occurrences, median, dispersion, slow_threshold_seconds=6 * DAY) is kind
    )


def test_each_kind_is_found_in_a_log_built_to_contain_it() -> None:
    """With a 6-day slow threshold every constructed transition lands in its intended kind."""
    analysis = analyze_bottlenecks(LOG, slow_threshold_seconds=6 * DAY)

    kinds = {(row.source, row.target): row.kind for row in analysis.transitions.itertuples()}
    assert kinds == {
        ("A", "B"): BottleneckKind.UNIFORMLY_SLOW,
        ("B", "C"): BottleneckKind.HIGH_VARIANCE,
        ("C", "D"): BottleneckKind.NOT_FLAGGED,
        ("D", "E"): BottleneckKind.INSUFFICIENT_DATA,
        ("E", "F"): BottleneckKind.SLOW_AND_VARIABLE,
    }


def test_distribution_columns_are_hand_computed() -> None:
    """B -> C: Q1 1 h, median midway between 1 h and 240 h, Q3 240 h, mean 120.5 h."""
    analysis = analyze_bottlenecks(LOG, slow_threshold_seconds=6 * DAY)

    assert tuple(analysis.transitions.columns) == BOTTLENECK_COLUMNS
    row = analysis.transitions.set_index(["source", "target"]).loc[("B", "C")]
    assert (row.occurrences, row.cases) == (40, 40)
    assert row.q1_seconds == pytest.approx(HOUR)
    assert row.p50_seconds == pytest.approx(120.5 * HOUR)
    assert row.q3_seconds == pytest.approx(240 * HOUR)
    assert row.mean_seconds == pytest.approx(120.5 * HOUR)
    assert row.dispersion == pytest.approx(239 / 241)


def test_most_costly_transition_and_time_shares() -> None:
    """E -> F totals 20*9 + 20*30 = 780 days, the largest share of the 1,382.9 days in the log."""
    analysis = analyze_bottlenecks(LOG, slow_threshold_seconds=6 * DAY)

    top = analysis.most_costly()
    total_days = 400 + (20 * HOUR + 20 * 10 * DAY) / DAY + 40 * HOUR / DAY + 10 * HOUR / DAY + 780
    assert (top.source, top.target) == ("E", "F")
    assert top.total_seconds == pytest.approx(780 * DAY)
    assert analysis.total_seconds == pytest.approx(total_days * DAY)
    assert analysis.transitions["share_of_total_time"].sum() == pytest.approx(1.0)
    assert list(analysis.flagged(BottleneckKind.UNIFORMLY_SLOW)["source"]) == ["A"]


def test_default_slow_threshold_is_a_quantile_of_eligible_transition_medians() -> None:
    """Medians of the four classifiable transitions: 1 h, 120.5 h, 240 h, 468 h.

    The 75th percentile (position 2.25) is 240 + 0.25 * 228 = 297 h; the rare D -> E is excluded.
    """
    analysis = analyze_bottlenecks(LOG)

    assert analysis.slow_threshold_seconds == pytest.approx(297 * HOUR)


def test_total_transition_time_equals_total_cycle_time() -> None:
    """Consecutive waits telescope: within a case they add up to last event minus first event.

    So bottleneck totals must equal Module A's summed cycle times. A mismatch would mean the two
    modules disagree about what time exists in the log.
    """
    variants = analyze_variants(DAY3_LOG)
    cycle_seconds = case_statistics(DAY3_LOG, variants)["cycle_time_seconds"].sum()

    assert analyze_bottlenecks(DAY3_LOG).total_seconds == pytest.approx(cycle_seconds)


@pytest.mark.integration
@pytest.mark.skipif(
    not get_settings().event_log_csv.exists(), reason="run `python -m meridian.discovery` first"
)
def test_real_log_bottlenecks_reconcile_with_cycle_times() -> None:
    """On BPI 2017: time shares sum to 1 and total elapsed time equals summed case cycle times."""
    log = read_event_log_csv(get_settings().event_log_csv)
    cycle_seconds = case_statistics(log, analyze_variants(log))["cycle_time_seconds"].sum()

    analysis = analyze_bottlenecks(log)

    assert analysis.total_seconds == pytest.approx(cycle_seconds, rel=1e-9)
    assert analysis.transitions["share_of_total_time"].sum() == pytest.approx(1.0)
    assert analysis.transitions["occurrences"].sum() == len(log) - log[schema.CASE_ID].nunique()


def test_invalid_inputs_are_rejected() -> None:
    """A quantile outside (0, 1) or a log without transitions cannot be analysed."""
    with pytest.raises(ValueError, match="slow_quantile"):
        analyze_bottlenecks(LOG, slow_quantile=1.0)
    single_events = LOG.groupby(schema.CASE_ID).head(1)
    with pytest.raises(ValueError, match="no transitions"):
        analyze_bottlenecks(single_events)
