"""Tests for variant analysis on logs whose variants and coverage are known by construction."""

import pandas as pd
import pytest
from test_dfg import LOG as DAY3_LOG
from test_heuristic_miner import log_from_variants

from meridian.discovery.variants import (
    CASE_COUNT,
    CUMULATIVE_SHARE,
    VARIANT,
    VARIANT_COLUMNS,
    analyze_variants,
    variants_needed,
)

# 10 cases in 4 variants: 5 / 3 / 1 / 1.
VARIANTS = {
    ("A", "B", "C"): 5,
    ("A", "C", "B"): 3,
    ("A", "B"): 1,
    ("A", "C"): 1,
}
ANALYSIS = analyze_variants(log_from_variants(VARIANTS))


def test_variant_table_counts_shares_and_ranks() -> None:
    """Most frequent first; equally frequent variants ordered by text so ranks are stable."""
    table = ANALYSIS.variants

    assert tuple(table.columns) == VARIANT_COLUMNS
    assert table[VARIANT].tolist() == ["A > B > C", "A > C > B", "A > B", "A > C"]
    assert table[CASE_COUNT].tolist() == [5, 3, 1, 1]
    assert table[CUMULATIVE_SHARE].tolist() == pytest.approx([0.5, 0.8, 0.9, 1.0])
    assert table["length"].tolist() == [3, 3, 2, 2]
    assert ANALYSIS.variant_count == 4
    assert ANALYSIS.case_count == 10


@pytest.mark.parametrize(("share", "expected"), [(0.5, 1), (0.8, 2), (0.81, 3), (0.9, 3), (1.0, 4)])
def test_variants_to_cover_share_of_cases(share: float, expected: int) -> None:
    """Coverage 5, 8, 9, 10 cases: 80% needs exactly 2 variants, 81% (8.1 -> 9 cases) needs 3."""
    assert ANALYSIS.variants_to_cover(share) == expected


@pytest.mark.parametrize("share", [0.0, -0.1, 1.5])
def test_coverage_share_outside_range_is_rejected(share: float) -> None:
    """A share of 0 or above 1 has no meaningful answer."""
    with pytest.raises(ValueError):
        ANALYSIS.variants_to_cover(share)


def test_variants_needed_works_from_saved_counts_alone() -> None:
    """The API answers from variants.csv; the standalone function must agree with the analysis."""
    assert variants_needed([5, 3, 1, 1], 0.8) == ANALYSIS.variants_to_cover(0.8) == 2
    assert variants_needed([], 0.8) == 0


def test_each_case_is_mapped_to_its_variant_rank() -> None:
    """Per-case happy-path checks rely on knowing each case's variant."""
    ranks = ANALYSIS.case_variants

    assert len(ranks) == 10
    assert ranks.value_counts().sort_index().tolist() == [5, 3, 1, 1]


def test_variants_use_event_order_not_row_order() -> None:
    """Shuffled rows give the same variants, since order comes from case and event_index."""
    log = log_from_variants(VARIANTS)

    shuffled = analyze_variants(log.sample(frac=1.0, random_state=5))

    pd.testing.assert_frame_equal(shuffled.variants, ANALYSIS.variants)


def test_day3_log_has_six_single_case_variants() -> None:
    """Every case in the Day 3 log takes a different path, so 80% coverage needs 5 of 6 variants."""
    analysis = analyze_variants(DAY3_LOG)

    assert analysis.variant_count == 6
    assert analysis.variants[CASE_COUNT].tolist() == [1] * 6
    assert analysis.variants_to_cover(0.8) == 5  # 4.8 cases rounds up to 5
