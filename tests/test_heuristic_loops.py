"""Tests for loop measures and the A, B, A pattern counts that length-two loops rely on."""

import pytest
from test_dfg import make_log

from meridian.discovery.heuristic_miner import (
    count_length_two_patterns,
    length_one_loop_measure,
    length_two_loop_measure,
)


@pytest.mark.parametrize(("repeats", "expected"), [(0, 0.0), (1, 0.5), (9, 0.9), (99, 0.99)])
def test_length_one_loop_measure(repeats: int, expected: float) -> None:
    """|A>A| / (|A>A| + 1): nine immediate repetitions reach the default 0.9 threshold."""
    assert length_one_loop_measure(repeats) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("a_b_a", "b_a_b", "expected"),
    [(0, 0, 0.0), (1, 0, 0.5), (5, 4, 0.9), (3_913, 3_913, 7_826 / 7_827)],
)
def test_length_two_loop_measure(a_b_a: int, b_a_b: int, expected: float) -> None:
    """(|A>>B| + |B>>A|) / (... + 1); the last row is BPI 2017's O_Create Offer / O_Created."""
    assert length_two_loop_measure(a_b_a, b_a_b) == pytest.approx(expected)


def test_loop_measures_reject_negative_counts() -> None:
    """Counts come from the log and cannot be negative; a negative one means a bug upstream."""
    with pytest.raises(ValueError):
        length_one_loop_measure(-1)
    with pytest.raises(ValueError):
        length_two_loop_measure(2, -1)


def test_counts_overlapping_return_patterns() -> None:
    """A B A B A holds A,B,A twice (positions 0-2 and 2-4) and B,A,B once (1-3)."""
    log = make_log(
        {"c1": [("A", "09:00"), ("B", "09:01"), ("A", "09:02"), ("B", "09:03"), ("A", "09:04")]}
    )

    assert count_length_two_patterns(log) == {("A", "B"): 2, ("B", "A"): 1}


def test_patterns_never_span_cases_or_count_immediate_repeats() -> None:
    """A,B at the end of one case plus A at the start of the next is not a loop; nor is A,A,A."""
    log = make_log(
        {
            "c1": [("A", "09:00"), ("B", "09:01")],
            "c2": [("A", "09:00"), ("C", "09:01")],
            "c3": [("A", "09:00"), ("A", "09:01"), ("A", "09:02")],
        }
    )

    assert count_length_two_patterns(log) == {}


def test_pattern_counts_use_event_order_not_row_order() -> None:
    """Shuffled rows must give the same counts, since order comes from case and event_index."""
    log = make_log({"c1": [("A", "09:00"), ("B", "09:01"), ("A", "09:02")]})

    shuffled = log.sample(frac=1.0, random_state=3)

    assert count_length_two_patterns(shuffled) == {("A", "B"): 1}
