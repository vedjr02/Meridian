"""Tests for the heuristic miner core: dependency measure, footprint classes, causal edges.

`VARIANTS` is built so that each footprint class appears for a known pair, with the dependency
value worked out by hand next to each expectation.
"""

import math

import pandas as pd
import pytest
from test_dfg import LOG as DAY3_LOG

from meridian.discovery.dfg import build_dfg
from meridian.discovery.heuristic_miner import (
    CAUSAL_EDGE_COLUMNS,
    Relation,
    causal_edges,
    classify_pair,
    dependency_matrix,
    dependency_measure,
    footprint_matrix,
)
from meridian.ingestion import schema

VARIANTS = {
    ("A", "B", "C", "E"): 10,  # with the next variant, B and C occur in both orders
    ("A", "C", "B", "E"): 10,
    ("A", "D", "E"): 12,  # A->D and D->E: 12 against 0
    ("F", "G"): 50,  # dominant direction ...
    ("G", "F"): 1,  # ... with one reverse observation (noise)
    ("A", "H", "E"): 3,  # observed one way only, but rarely
    ("J", "K"): 9,  # exactly at the 0.9 threshold
    ("L", "M"): 8,  # just below it
}


def log_from_variants(variants: dict[tuple[str, ...], int]) -> pd.DataFrame:
    """Expand variant counts into a normalized-schema log, one minute between events."""
    rows = []
    case_number = 0
    for activities, count in variants.items():
        for _ in range(count):
            case_number += 1
            start = pd.Timestamp("2016-01-01T00:00:00Z") + pd.Timedelta(days=case_number)
            rows += [
                (f"case{case_number}", i, a, start + pd.Timedelta(minutes=i), "u", None, None)
                for i, a in enumerate(activities)
            ]
    return pd.DataFrame(rows, columns=list(schema.NORMALIZED_COLUMNS))


DFG = build_dfg(log_from_variants(VARIANTS))


@pytest.mark.parametrize(
    ("a_to_b", "b_to_a", "expected"),
    [
        (0, 0, 0.0),
        (1, 0, 0.5),  # a single observation is weak evidence
        (9, 0, 0.9),
        (50, 1, 49 / 52),
        (3, 3, 0.0),  # balanced: no direction
        (0, 5, -5 / 6),
    ],
)
def test_dependency_measure_matches_formula(a_to_b: int, b_to_a: int, expected: float) -> None:
    """(|A>B| - |B>A|) / (|A>B| + |B>A| + 1), checked on hand-computed values."""
    assert dependency_measure(a_to_b, b_to_a) == pytest.approx(expected)


def test_dependency_measure_is_antisymmetric() -> None:
    """dep(A, B) = -dep(B, A); the footprint's mirror consistency depends on this."""
    for a_to_b, b_to_a in [(7, 2), (0, 4), (13, 13)]:
        assert dependency_measure(a_to_b, b_to_a) == -dependency_measure(b_to_a, a_to_b)


def test_dependency_measure_rejects_negative_counts() -> None:
    """Counts come from the DFG and can never be negative; if they are, something upstream broke."""
    with pytest.raises(ValueError):
        dependency_measure(-1, 3)


@pytest.mark.parametrize(
    ("a", "b", "relation"),
    [
        ("A", "B", Relation.CAUSES),  # 10 vs 0 -> 10/11 = 0.909
        ("B", "A", Relation.CAUSED_BY),
        ("B", "C", Relation.PARALLEL),  # 10 vs 10 -> 0.0
        ("A", "D", Relation.CAUSES),  # 12 vs 0 -> 12/13 = 0.923
        ("F", "G", Relation.CAUSES),  # 50 vs 1 -> 49/52 = 0.942, causal despite noise
        ("G", "F", Relation.CAUSED_BY),
        ("A", "H", Relation.INFREQUENT),  # 3 vs 0 -> 0.75
        ("J", "K", Relation.CAUSES),  # 9 vs 0 -> 0.9, boundary is inclusive
        ("L", "M", Relation.INFREQUENT),  # 8 vs 0 -> 0.889
        ("B", "D", Relation.UNRELATED),  # never adjacent
        ("A", "F", Relation.UNRELATED),
    ],
)
def test_footprint_classifies_each_pair_as_expected(a: str, b: str, relation: Relation) -> None:
    """Every footprint class on a pair whose counts, and so whose answer, are known."""
    assert footprint_matrix(DFG).loc[a, b] == relation.value


def test_footprint_matrix_is_mirror_consistent() -> None:
    """A -> B must appear as B <- A; symmetric relations must match in both cells."""
    matrix = footprint_matrix(DFG)
    mirror = {"->": "<-", "<-": "->", "||": "||", "#": "#", "~": "~"}

    for a in matrix.index:
        for b in matrix.columns:
            if a != b:
                assert matrix.loc[b, a] == mirror[matrix.loc[a, b]]
            else:
                assert matrix.loc[a, b] is None


def test_lower_threshold_admits_weaker_evidence() -> None:
    """The threshold is the noise dial: at 0.7, A->H (0.75) becomes causal; at 0.9 it is not."""
    assert classify_pair(3, 0, threshold=0.9) is Relation.INFREQUENT
    assert classify_pair(3, 0, threshold=0.7) is Relation.CAUSES


@pytest.mark.parametrize("threshold", [0.0, 1.0, 1.2])
def test_unusable_threshold_is_rejected(threshold: float) -> None:
    """A threshold of 1 can never be reached, and 0 accepts pairs with no evidence."""
    with pytest.raises(ValueError):
        classify_pair(5, 0, threshold=threshold)


def test_dependency_matrix_values_and_empty_diagonal() -> None:
    """Matrix cells equal the formula on DFG counts; self-pairs are left to loop detection."""
    matrix = dependency_matrix(DFG)

    assert matrix.loc["F", "G"] == pytest.approx(49 / 52)
    assert matrix.loc["G", "F"] == pytest.approx(-49 / 52)
    assert matrix.loc["B", "D"] == 0.0
    assert all(math.isnan(matrix.loc[a, a]) for a in matrix.index)


def test_causal_edges_are_exactly_the_pairs_at_or_above_threshold() -> None:
    """The mined model's edges: eight pairs reach 0.9; parallel, rare and unrelated pairs do not."""
    edges = causal_edges(DFG)

    assert tuple(edges.columns) == CAUSAL_EDGE_COLUMNS
    assert [(row.source, row.target) for row in edges.itertuples()] == [
        ("A", "B"),
        ("A", "C"),
        ("A", "D"),
        ("B", "E"),
        ("C", "E"),
        ("D", "E"),
        ("F", "G"),
        ("J", "K"),
    ]
    f_to_g = edges[(edges.source == "F") & (edges.target == "G")].iloc[0]
    assert f_to_g.dependency == pytest.approx(49 / 52)
    assert f_to_g.frequency == 50


def test_day3_synthetic_log_classifications() -> None:
    """Same log as the DFG tests (04-BUILD-PLAN Day 4): sparse evidence stays below 0.9.

    A->B 4 vs B->A 1 (0.5) and B->C 2 vs C->B 1 (0.25) are parallel; C->D 2 vs 0 (0.667) is
    infrequent at 0.9 but causal at 0.6; A and D never directly follow each other.
    """
    dfg = build_dfg(DAY3_LOG)

    at_default = footprint_matrix(dfg)
    assert at_default.loc["A", "B"] == Relation.PARALLEL
    assert at_default.loc["B", "C"] == Relation.PARALLEL
    assert at_default.loc["C", "D"] == Relation.INFREQUENT
    assert at_default.loc["A", "D"] == Relation.UNRELATED
    assert causal_edges(dfg).empty

    assert footprint_matrix(dfg, threshold=0.6).loc["C", "D"] == Relation.CAUSES
