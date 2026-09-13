"""Heuristic Miner, implemented from first principles (02-TECH-STACK-AND-SKILLS.md, section 1).

This file holds the core: the dependency measure, the footprint matrix, and the threshold that
turns dependencies into causal edges. Loop handling (length-one and length-two loops) and the
assembled process model (start activities, end activities, causal edges) build on it.

All counts come from `DirectlyFollowsGraph.frequency`, so the miner never re-derives |A>B| from
raw events and cannot disagree with the DFG it is based on.
"""

from __future__ import annotations

from enum import StrEnum

import numpy as np
import pandas as pd

from meridian.config import DEFAULT_DEPENDENCY_THRESHOLD, validate_dependency_threshold
from meridian.discovery.dfg import FREQUENCY, SOURCE, TARGET, DirectlyFollowsGraph
from meridian.ingestion import schema

DEPENDENCY = "dependency"
CAUSAL_EDGE_COLUMNS = (SOURCE, TARGET, DEPENDENCY, FREQUENCY)


class Relation(StrEnum):
    """Footprint relation of a row activity A to a column activity B.

    CAUSES, CAUSED_BY, PARALLEL and UNRELATED are the footprint classes named in
    02-TECH-STACK-AND-SKILLS.md (causal in either direction, parallel, unrelated). INFREQUENT is
    the one addition, needed once a threshold is applied: B directly follows A and never the
    reverse, but too rarely for the dependency measure to reach the threshold. Calling that
    "causal" would let noise into the model; calling it "unrelated" would misstate the log, which
    does contain the pair.
    """

    CAUSES = "->"
    CAUSED_BY = "<-"
    PARALLEL = "||"
    UNRELATED = "#"
    INFREQUENT = "~"


def dependency_measure(a_to_b: int, b_to_a: int) -> float:
    """Return the dependency of A on B: (|A>B| - |B>A|) / (|A>B| + |B>A| + 1).

    Why this formula rather than presence-only footprints: it grades direction instead of
    treating one stray reverse observation as proof of parallelism. It approaches +1 as A>B
    dominates, -1 as B>A dominates, and 0 when both are equally common. The +1 in the denominator
    discounts thin evidence: one observation scores 0.5, not a certain-looking 1.0. That tolerance
    for noise is what distinguishes the heuristic miner from the Alpha algorithm.
    """
    if a_to_b < 0 or b_to_a < 0:
        raise ValueError(f"Directly-follows counts cannot be negative: {a_to_b}, {b_to_a}")
    return (a_to_b - b_to_a) / (a_to_b + b_to_a + 1)


def classify_pair(
    a_to_b: int, b_to_a: int, threshold: float = DEFAULT_DEPENDENCY_THRESHOLD
) -> Relation:
    """Classify how activity A relates to activity B from their directly-follows counts.

    Decision order, and why it is this order:
    1. Neither direction observed: UNRELATED.
    2. Dependency at or beyond the threshold in either direction: CAUSES or CAUSED_BY. This is
       checked before parallelism so that a dominant direction with occasional reverse noise
       (50 against 1 scores 0.94) counts as causal, not parallel.
    3. Both directions observed without either dominating: PARALLEL.
    4. Only one direction observed, below the threshold: INFREQUENT.

    Known limitation, resolved by loop detection: a length-two loop (A, B, A) produces both A>B
    and B>A, so on its own this classification reads such a loop as PARALLEL.
    """
    validate_dependency_threshold(threshold)
    if a_to_b == 0 and b_to_a == 0:
        return Relation.UNRELATED
    dependency = dependency_measure(a_to_b, b_to_a)
    if dependency >= threshold:
        return Relation.CAUSES
    if dependency <= -threshold:
        return Relation.CAUSED_BY
    if a_to_b > 0 and b_to_a > 0:
        return Relation.PARALLEL
    return Relation.INFREQUENT


def _activities(dfg: DirectlyFollowsGraph) -> list[str]:
    """Activities in a fixed alphabetical order, so matrices are identical across runs."""
    return sorted(dfg.activity_counts)


def dependency_matrix(dfg: DirectlyFollowsGraph) -> pd.DataFrame:
    """Dependency measure for every ordered pair of distinct activities (row A, column B).

    Why the diagonal is empty (NaN): A followed by A is a length-one loop. The pairwise formula
    would score every activity against itself as 0 (|A>A| - |A>A| = 0), so self-dependency needs
    its own measure, |A>A| / (|A>A| + 1), applied by loop detection instead.
    """
    activities = _activities(dfg)
    values = [
        [
            np.nan if a == b else dependency_measure(dfg.frequency(a, b), dfg.frequency(b, a))
            for b in activities
        ]
        for a in activities
    ]
    return pd.DataFrame(values, index=activities, columns=activities, dtype="float64")


def footprint_matrix(
    dfg: DirectlyFollowsGraph, threshold: float = DEFAULT_DEPENDENCY_THRESHOLD
) -> pd.DataFrame:
    """Relation of every row activity to every column activity, as `Relation` symbols.

    The matrix is mirror-consistent by construction: if A CAUSES B then B is CAUSED_BY A, and
    PARALLEL, UNRELATED and INFREQUENT are symmetric. The diagonal is left empty for the same
    reason as in `dependency_matrix`.
    """
    validate_dependency_threshold(threshold)
    activities = _activities(dfg)
    values = [
        [
            None
            if a == b
            else classify_pair(dfg.frequency(a, b), dfg.frequency(b, a), threshold).value
            for b in activities
        ]
        for a in activities
    ]
    return pd.DataFrame(values, index=activities, columns=activities, dtype="object")


def causal_edges(
    dfg: DirectlyFollowsGraph, threshold: float = DEFAULT_DEPENDENCY_THRESHOLD
) -> pd.DataFrame:
    """Return the pairs whose dependency reaches the threshold: the edges of the mined model.

    Why only observed DFG edges are examined: a causal edge needs |A>B| > 0, so iterating the
    DFG's edges (159 on BPI 2017) instead of every pair of activities cannot miss one. Self-loops
    are skipped here; loop detection decides those.

    Columns are `CAUSAL_EDGE_COLUMNS`, sorted by source then target for deterministic output.
    """
    validate_dependency_threshold(threshold)
    rows = []
    for source, target, frequency in dfg.edges[[SOURCE, TARGET, FREQUENCY]].itertuples(
        index=False, name=None
    ):
        if source == target:
            continue
        dependency = dependency_measure(int(frequency), dfg.frequency(target, source))
        if dependency >= threshold:
            rows.append((source, target, dependency, int(frequency)))
    edges = pd.DataFrame(rows, columns=list(CAUSAL_EDGE_COLUMNS))
    return edges.sort_values([SOURCE, TARGET], kind="stable").reset_index(drop=True)


def length_one_loop_measure(a_to_a: int) -> float:
    """Return the self-loop measure |A>A| / (|A>A| + 1).

    Why a separate formula: the pairwise dependency of an activity with itself is always 0
    (|A>A| - |A>A|), so it can never detect an activity immediately repeated. This measure grows
    toward 1 with the number of immediate repetitions, with the same +1 discount on thin evidence.
    """
    if a_to_a < 0:
        raise ValueError(f"Directly-follows counts cannot be negative: {a_to_a}")
    return a_to_a / (a_to_a + 1)


def length_two_loop_measure(a_b_a: int, b_a_b: int) -> float:
    """Return the length-two loop measure (|A>>B| + |B>>A|) / (|A>>B| + |B>>A| + 1).

    |A>>B| counts A, B, A as three consecutive events in one case. Why it is needed: a loop
    A -> B -> A produces both A>B and B>A, which drags the pairwise dependency toward 0 and makes
    the loop look like parallelism. Activities that are genuinely parallel and executed once each
    never produce the return pattern A, B, A, so counting the pattern tells the two apart.
    """
    if a_b_a < 0 or b_a_b < 0:
        raise ValueError(f"Pattern counts cannot be negative: {a_b_a}, {b_a_b}")
    return (a_b_a + b_a_b) / (a_b_a + b_a_b + 1)


def count_length_two_patterns(event_log: pd.DataFrame) -> dict[tuple[str, str], int]:
    """Count |A>>B| for every pair: how often A, B, A occur as consecutive events in one case.

    Why from the event log and not the DFG: the DFG keeps only pairs, and the return pattern needs
    three consecutive events. Events are ordered by (case_id, event_index), as everywhere else.
    Patterns never span two cases, and A, A, A is not counted: an immediate repetition is a
    length-one loop and is measured separately.
    """
    log = (
        event_log.loc[:, [schema.CASE_ID, schema.EVENT_INDEX, schema.ACTIVITY]]
        .sort_values([schema.CASE_ID, schema.EVENT_INDEX], kind="stable")
        .reset_index(drop=True)
    )
    activity = log[schema.ACTIVITY]
    middle = activity.shift(-1)
    # Rows are grouped by case, so events i and i+2 sharing a case means i+1 shares it too.
    same_case = log[schema.CASE_ID].eq(log[schema.CASE_ID].shift(-2))
    returns = (
        same_case.to_numpy(dtype=bool, na_value=False)
        & activity.eq(activity.shift(-2)).to_numpy(dtype=bool, na_value=False)
        & activity.ne(middle).to_numpy(dtype=bool, na_value=False)
    )
    pairs = pd.DataFrame({"a": activity[returns].to_numpy(), "b": middle[returns].to_numpy()})
    counts = pairs.groupby(["a", "b"]).size()
    return {(str(a), str(b)): int(count) for (a, b), count in counts.items()}
