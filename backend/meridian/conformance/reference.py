"""Reference model selection: which process the real cases are checked against.

01-REQUIREMENTS.md Module B req. 1: use the most frequent variant from Module A, or a documented
intended process if the dataset provides one, and log which was used. Every reference model built
here carries a description of how it was chosen, so each downstream number can state what it was
measured against.

Open decision (08-OPEN-QUESTIONS.md, "The most common variant is a cancellation path"): on BPI 2017
the most frequent variant ends cancelled. A second strategy therefore picks the most frequent
variant among cases with a given outcome. Both are implemented here; which one the pipeline uses is
Ved's decision, not this module's.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from meridian.conformance.petri_net import PetriNet, sequence_net
from meridian.discovery.variants import CASE_COUNT, analyze_variants
from meridian.ingestion import schema


class ReferenceStrategy(StrEnum):
    """How the reference process was chosen."""

    MOST_FREQUENT_VARIANT = "most_frequent_variant"
    MOST_FREQUENT_VARIANT_FOR_OUTCOME = "most_frequent_variant_for_outcome"
    DOCUMENTED = "documented"


@dataclass(frozen=True)
class ReferenceModel:
    """The process cases are replayed against, and a record of how it was chosen.

    Attributes:
        activities: The reference sequence.
        net: Its Petri net, as used by token replay.
        strategy: Which selection rule produced it.
        description: One sentence stating the choice and the evidence behind it, for reports.
        supporting_cases: Cases that follow the reference exactly (None for a documented model,
            which is not derived from the log).
        eligible_cases: Cases the choice was made from (None for a documented model).
    """

    activities: tuple[str, ...]
    net: PetriNet
    strategy: ReferenceStrategy
    description: str
    supporting_cases: int | None
    eligible_cases: int | None


def select_reference_model(
    event_log: pd.DataFrame,
    strategy: ReferenceStrategy,
    *,
    outcome: str | None = None,
    documented_activities: Sequence[str] | None = None,
) -> ReferenceModel:
    """Choose the reference process by `strategy` and build its Petri net.

    Args:
        event_log: Normalized event log (as read by `read_event_log_csv`).
        strategy: Selection rule; see `ReferenceStrategy`.
        outcome: Required for `MOST_FREQUENT_VARIANT_FOR_OUTCOME`: only cases with this outcome
            are considered.
        documented_activities: Required for `DOCUMENTED`: the intended sequence from process
            documentation.

    Why an explicit strategy argument with no default: the choice changes every conformance number,
    so library callers must state it rather than inherit one silently. The project's decision
    (most frequent variant, 08-OPEN-QUESTIONS.md) is the command's default, not this function's.
    """
    if strategy is ReferenceStrategy.DOCUMENTED:
        if not documented_activities:
            raise ValueError("The documented strategy needs documented_activities")
        activities = tuple(documented_activities)
        return ReferenceModel(
            activities=activities,
            net=sequence_net(activities),
            strategy=strategy,
            description=f"Documented intended process of {len(activities)} activities.",
            supporting_cases=None,
            eligible_cases=None,
        )

    if strategy is ReferenceStrategy.MOST_FREQUENT_VARIANT_FOR_OUTCOME:
        if outcome is None:
            raise ValueError("The outcome strategy needs an outcome")
        with_outcome = event_log[schema.OUTCOME].eq(outcome).to_numpy(dtype=bool, na_value=False)
        candidates = event_log[with_outcome]
        if candidates.empty:
            raise ValueError(f"No cases have outcome {outcome!r}; cannot select a reference model")
    else:
        candidates = event_log

    variants = analyze_variants(candidates)
    activities = variants.sequence(1)
    supporting = int(variants.variants[CASE_COUNT].iloc[0])
    eligible = variants.case_count
    share = supporting / eligible
    if strategy is ReferenceStrategy.MOST_FREQUENT_VARIANT:
        description = (
            f"Most frequent variant across all {eligible:,} cases: {supporting:,} cases "
            f"({share:.1%}) follow its {len(activities)} activities exactly."
        )
    else:
        description = (
            f"Most frequent variant among the {eligible:,} cases with outcome '{outcome}': "
            f"{supporting:,} cases ({share:.1%}) follow its {len(activities)} activities exactly."
        )
    return ReferenceModel(
        activities=activities,
        net=sequence_net(activities),
        strategy=strategy,
        description=description,
        supporting_cases=supporting,
        eligible_cases=eligible,
    )
