"""Tests for reference model selection.

`LOG`: the most frequent variant overall (6 cases) ends cancelled, while cases that end approved
mostly follow a different path (4 of 5) — the same shape as the BPI 2017 finding that prompted the
outcome strategy.
"""

import pandas as pd
import pytest
from test_heuristic_miner import log_from_variants

from meridian.conformance.reference import ReferenceStrategy, select_reference_model
from meridian.ingestion import schema

SPEC = [
    (("Submit", "Offer", "Cancel"), 6, "cancelled"),
    (("Submit", "Offer", "Accept", "Approve"), 4, "approved"),
    (("Submit", "Accept", "Offer", "Approve"), 1, "approved"),
    (("Submit", "Offer"), 2, None),
]


def build_log() -> pd.DataFrame:
    """Expand SPEC into a normalized log and attach each variant's outcome to its cases."""
    log = log_from_variants({activities: count for activities, count, _ in SPEC})
    outcomes = {}
    case_number = 0
    for _, count, outcome in SPEC:
        for _ in range(count):
            case_number += 1
            outcomes[f"case{case_number}"] = outcome
    log[schema.OUTCOME] = log[schema.CASE_ID].map(outcomes).astype("string")
    return log


LOG = build_log()


def test_most_frequent_variant_follows_the_requirement_literally() -> None:
    """Rank 1 overall is the 6-case cancellation path, and the description says so with numbers."""
    reference = select_reference_model(LOG, ReferenceStrategy.MOST_FREQUENT_VARIANT)

    assert reference.activities == ("Submit", "Offer", "Cancel")
    assert (reference.supporting_cases, reference.eligible_cases) == (6, 13)
    assert reference.description == (
        "Most frequent variant across all 13 cases: "
        "6 cases (46.2%) follow its 3 activities exactly."
    )
    assert [t.label for t in reference.net.transitions] == ["Submit", "Offer", "Cancel"]


def test_outcome_strategy_picks_the_most_frequent_path_among_those_cases() -> None:
    """Among the 5 approved cases, 4 follow Submit, Offer, Accept, Approve."""
    reference = select_reference_model(
        LOG, ReferenceStrategy.MOST_FREQUENT_VARIANT_FOR_OUTCOME, outcome="approved"
    )

    assert reference.activities == ("Submit", "Offer", "Accept", "Approve")
    assert (reference.supporting_cases, reference.eligible_cases) == (4, 5)
    assert "cases with outcome 'approved'" in reference.description
    assert "4 cases (80.0%)" in reference.description


def test_outcome_strategy_requires_an_outcome_that_exists() -> None:
    """A missing or unknown outcome must fail loudly rather than fall back to all cases."""
    with pytest.raises(ValueError, match="needs an outcome"):
        select_reference_model(LOG, ReferenceStrategy.MOST_FREQUENT_VARIANT_FOR_OUTCOME)
    with pytest.raises(ValueError, match="No cases have outcome 'pending'"):
        select_reference_model(
            LOG, ReferenceStrategy.MOST_FREQUENT_VARIANT_FOR_OUTCOME, outcome="pending"
        )


def test_documented_model_uses_the_given_sequence() -> None:
    """A documented process is not derived from the log, so it reports no case support."""
    reference = select_reference_model(
        LOG, ReferenceStrategy.DOCUMENTED, documented_activities=["Submit", "Review", "Approve"]
    )

    assert reference.activities == ("Submit", "Review", "Approve")
    assert reference.supporting_cases is None
    assert reference.description == "Documented intended process of 3 activities."
    with pytest.raises(ValueError, match="needs documented_activities"):
        select_reference_model(LOG, ReferenceStrategy.DOCUMENTED)
