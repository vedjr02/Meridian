"""Tests for token-based replay against hand-computed token counts and fitness.

Reference A, B, C, D is the net p0 -A-> p1 -B-> p2 -C-> p3 -D-> p4, starting with one token in p0
and ending with one in p4. Each expectation below was traced by hand; the derivation sits beside
it as (produced, consumed, missing, remaining).
"""

import random

import pytest

from meridian.conformance.petri_net import sequence_net
from meridian.conformance.replay import replay_trace

NET = sequence_net(["A", "B", "C", "D"])


@pytest.mark.parametrize(
    ("trace", "counts", "fitness"),
    [
        # Perfect: every token consumed where expected. p = 1 + 4, c = 4 + 1.
        (["A", "B", "C", "D"], (5, 5, 0, 0), 1.0),
        # One skipped step: D finds p3 empty (missing 1); B's token in p2 is never used.
        (["A", "B", "D"], (4, 4, 1, 1), 0.75),
        # Two steps swapped: C finds p2 empty (missing 1); B's later token in p2 is left over.
        (["A", "C", "B", "D"], (5, 5, 1, 1), 0.8),
        # One step repeated: second B finds p1 empty (missing 1); one of two tokens in p2 left.
        (["A", "B", "B", "C", "D"], (6, 6, 1, 1), 5 / 6),
        # One extra activity unknown to the model: costs one missing and one remaining token.
        (["A", "B", "X", "C", "D"], (6, 6, 1, 1), 5 / 6),
        # Stopped early: final place p4 empty (missing 1); token in p2 left (remaining 1).
        (["A", "B"], (3, 3, 1, 1), 2 / 3),
        # Very different: two unknown steps, p4 never reached, initial token in p0 never used.
        (["X", "Y"], (3, 3, 3, 3), 0.0),
        # Empty case: final token missing, initial token remaining.
        ([], (1, 1, 1, 1), 0.0),
    ],
)
def test_token_counts_and_fitness_match_hand_derivation(
    trace: list[str], counts: tuple[int, int, int, int], fitness: float
) -> None:
    """Perfect, one-deviation and very-different cases (04-BUILD-PLAN Day 9)."""
    result = replay_trace(NET, trace)

    assert (result.produced, result.consumed, result.missing, result.remaining) == counts
    assert result.fitness == pytest.approx(fitness)
    assert result.fits is (fitness == 1.0)


def test_unknown_activities_are_counted() -> None:
    """Extra steps the model does not know are reported, not silently skipped."""
    assert replay_trace(NET, ["A", "X", "B", "Y", "C", "D"]).unknown_activities == 2


def test_repeated_reference_activity_fires_the_transition_that_needs_no_invented_token() -> None:
    """Reference A, B, A: the second A must fire t2 (its input holds a token), not t0 again."""
    net = sequence_net(["A", "B", "A"])

    result = replay_trace(net, ["A", "B", "A"])

    assert (result.missing, result.remaining, result.fitness) == (0, 0, 1.0)


def test_conservation_and_bounds_hold_for_random_traces() -> None:
    """For any trace: r - m == p - c, and fitness stays within [0, 1].

    Seeded random traces mix known, unknown, repeated and missing activities, covering far more
    shapes than the hand-derived cases while staying reproducible.
    """
    rng = random.Random(20260913)
    alphabet = ["A", "B", "C", "D", "X"]
    for _ in range(500):
        trace = [rng.choice(alphabet) for _ in range(rng.randint(0, 12))]

        result = replay_trace(NET, trace)

        assert result.remaining - result.missing == result.produced - result.consumed, trace
        assert 0.0 <= result.fitness <= 1.0, trace
        assert result.missing <= result.consumed and result.remaining <= result.produced
