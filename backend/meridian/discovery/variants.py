"""Variant analysis: the distinct end-to-end paths cases take, and how concentrated they are.

A variant is the exact sequence of activities a case performed. How many variants it takes to
cover most cases is the headline "your process is messier than you think" finding
(01-REQUIREMENTS.md, Module A requirement 5).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd

from meridian.ingestion import schema

VARIANT_RANK = "variant_rank"
VARIANT = "variant"
LENGTH = "length"
CASE_COUNT = "case_count"
CASE_SHARE = "case_share"
CUMULATIVE_SHARE = "cumulative_share"
VARIANT_COLUMNS = (VARIANT_RANK, VARIANT, LENGTH, CASE_COUNT, CASE_SHARE, CUMULATIVE_SHARE)

# Display form of a sequence. Variants are grouped on the activity tuple itself, so an activity
# name that happened to contain this separator could never merge two different variants.
SEPARATOR = " > "


@dataclass(frozen=True)
class VariantAnalysis:
    """Distinct variants with their frequencies, and which variant each case follows.

    Attributes:
        variants: Columns `VARIANT_COLUMNS`. Rank 1 is the most frequent variant; equally frequent
            variants are ordered by their display text so ranks are identical across runs.
        case_variants: Variant rank per case id.
        case_count: Number of cases analysed.
    """

    variants: pd.DataFrame
    case_variants: pd.Series
    case_count: int

    @property
    def variant_count(self) -> int:
        """Number of distinct end-to-end paths."""
        return len(self.variants)

    def variants_to_cover(self, share: float = 0.8) -> int:
        """Return the fewest most-frequent variants whose cases make up at least `share` of cases.

        Why this is the headline number: it measures how concentrated behaviour really is. A
        process described as one standard flow that needs hundreds of paths to cover 80% of cases
        has no dominant standard at all.

        Ties among equally frequent variants cannot change the answer, since whichever tied
        variant is counted first adds the same number of cases. The target case count is rounded
        up (80% of 31,509 cases is 25,207.2, so 25,208 cases must be covered) after trimming
        floating-point noise, so that 80% of 10 cases is exactly 8.
        """
        if not 0 < share <= 1:
            raise ValueError(f"Coverage share must be in (0, 1], got {share}")
        if self.case_count == 0:
            return 0
        needed = math.ceil(round(share * self.case_count, 9))
        cumulative = self.variants[CASE_COUNT].cumsum().to_numpy()
        return int(np.searchsorted(cumulative, needed, side="left")) + 1


def analyze_variants(event_log: pd.DataFrame) -> VariantAnalysis:
    """Group cases by their exact activity sequence and rank the resulting variants.

    Why sequences follow (case_id, event_index): as in the DFG, source order is the only reliable
    tiebreak for events sharing a timestamp, and a variant is only meaningful if the same case
    always yields the same sequence.
    """
    log = event_log.loc[:, [schema.CASE_ID, schema.EVENT_INDEX, schema.ACTIVITY]].sort_values(
        [schema.CASE_ID, schema.EVENT_INDEX], kind="stable"
    )
    sequences = log.groupby(schema.CASE_ID, sort=True)[schema.ACTIVITY].agg(tuple)

    counts = Counter(sequences.tolist())
    ordered = sorted(counts.items(), key=lambda item: (-item[1], SEPARATOR.join(item[0])))
    total = len(sequences)

    rank_of = {sequence: rank for rank, (sequence, _) in enumerate(ordered, start=1)}
    cumulative = 0
    rows = []
    for rank, (sequence, count) in enumerate(ordered, start=1):
        cumulative += count
        rows.append(
            (
                rank,
                SEPARATOR.join(sequence),
                len(sequence),
                count,
                count / total,
                cumulative / total,
            )
        )

    # A plain lookup rather than `Series.map(dict)`: pandas turns tuple dict keys into a
    # MultiIndex, which does not reliably match tuples of different lengths.
    case_variants = pd.Series(
        [rank_of[sequence] for sequence in sequences], index=sequences.index, name=VARIANT_RANK
    )
    return VariantAnalysis(
        variants=pd.DataFrame(rows, columns=list(VARIANT_COLUMNS)),
        case_variants=case_variants,
        case_count=total,
    )
