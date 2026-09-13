"""Heuristic Miner, implemented from first principles (02-TECH-STACK-AND-SKILLS.md, section 1).

This file holds the core: the dependency measure, the footprint matrix, and the threshold that
turns dependencies into causal edges. Loop handling (length-one and length-two loops) and the
assembled process model (start activities, end activities, causal edges) build on it.

All counts come from `DirectlyFollowsGraph.frequency`, so the miner never re-derives |A>B| from
raw events and cannot disagree with the DFG it is based on.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

from meridian.config import (
    DEFAULT_DEPENDENCY_THRESHOLD,
    get_settings,
    validate_dependency_threshold,
)
from meridian.discovery.dfg import FREQUENCY, SOURCE, TARGET, DirectlyFollowsGraph, build_dfg
from meridian.ingestion import schema
from meridian.ingestion.io import read_event_log_csv

DEPENDENCY = "dependency"
CAUSAL_EDGE_COLUMNS = (SOURCE, TARGET, DEPENDENCY, FREQUENCY)

# Which rule admitted an edge into the mined model (see `mine_heuristic_net`).
KIND = "kind"
CAUSAL = "causal"
LENGTH_ONE_LOOP = "length_one_loop"
LENGTH_TWO_LOOP = "length_two_loop"
BEST_CONNECTION = "best_connection"
MODEL_EDGE_COLUMNS = (SOURCE, TARGET, KIND, DEPENDENCY, FREQUENCY)


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


@dataclass(frozen=True)
class HeuristicNet:
    """The mined process model: start activities, end activities and admitted edges.

    Attributes:
        activities: Event count per activity; the model's nodes.
        start_activities: Number of cases starting with each activity.
        end_activities: Number of cases ending with each activity.
        edges: Columns `MODEL_EDGE_COLUMNS`, sorted by source then target. `kind` names the rule
            that admitted the edge, and `dependency` holds that rule's measure: the pairwise
            dependency for `causal` and `best_connection`, the self-loop measure for
            `length_one_loop`, the return-pattern measure for `length_two_loop`.
        threshold: Dependency threshold the model was mined with.
        case_count: Number of cases in the log.
    """

    activities: dict[str, int]
    start_activities: dict[str, int]
    end_activities: dict[str, int]
    edges: pd.DataFrame
    threshold: float
    case_count: int

    @property
    def orphan_activities(self) -> list[str]:
        """Activities with no edge to or from another activity (a self-loop connects nothing).

        Why it matters: an orphan occurred in the log but has no place in the drawn process, which
        is the first plausibility check on a mined model (04-BUILD-PLAN.md, Day 5).
        """
        linked = self.edges[self.edges[SOURCE] != self.edges[TARGET]]
        return sorted(set(self.activities) - set(linked[SOURCE]) - set(linked[TARGET]))

    def to_dict(self) -> dict:
        """Return a JSON-serialisable form for `heuristic_net.json` and the frontend."""
        return {
            "threshold": self.threshold,
            "case_count": self.case_count,
            "activities": self.activities,
            "start_activities": self.start_activities,
            "end_activities": self.end_activities,
            "edges": [
                {SOURCE: s, TARGET: t, KIND: k, DEPENDENCY: float(d), FREQUENCY: int(f)}
                for s, t, k, d, f in self.edges[list(MODEL_EDGE_COLUMNS)].itertuples(
                    index=False, name=None
                )
            ],
        }


def mine_heuristic_net(
    event_log: pd.DataFrame,
    threshold: float = DEFAULT_DEPENDENCY_THRESHOLD,
    *,
    connect_all: bool = True,
) -> HeuristicNet:
    """Mine the heuristic process model from a normalized event log.

    Edges are admitted by four rules, applied in order; `kind` records which one applied:
    1. `causal`: pairwise dependency at or above the threshold.
    2. `length_one_loop`: self-loop measure at or above the threshold.
    3. `length_two_loop`: return-pattern measure at or above the threshold admits both A->B and
       B->A, keeping any direction already admitted as causal. This is what stops a loop being
       read as parallelism.
    4. `best_connection` (when `connect_all`): an activity left without an incoming edge, and not
       a start activity, gets its strongest observed incoming pair; likewise outgoing edges for
       non-end activities. Why: one global threshold can leave a rare activity with every link
       below the bar, disconnected from a process the log clearly shows it belongs to. This is
       the HeuristicsMiner's "all activities connected" heuristic, kept visibly distinct from
       threshold-backed edges by its kind.

    Why one threshold for all measures: a single setting then controls how much evidence any
    edge needs, which keeps the model's strictness explainable in one sentence.
    """
    validate_dependency_threshold(threshold)
    dfg = build_dfg(event_log)
    admitted: dict[tuple[str, str], tuple[str, float, int]] = {}

    for source, target, dependency, frequency in causal_edges(dfg, threshold).itertuples(
        index=False, name=None
    ):
        admitted[(source, target)] = (CAUSAL, dependency, frequency)

    for activity in sorted(dfg.activity_counts):
        repeats = dfg.frequency(activity, activity)
        measure = length_one_loop_measure(repeats)
        if repeats and measure >= threshold:
            admitted[(activity, activity)] = (LENGTH_ONE_LOOP, measure, repeats)

    patterns = count_length_two_patterns(event_log)
    for a, b in sorted({tuple(sorted(pair)) for pair in patterns}):
        measure = length_two_loop_measure(patterns.get((a, b), 0), patterns.get((b, a), 0))
        if measure >= threshold:
            for source, target in ((a, b), (b, a)):
                admitted.setdefault(
                    (source, target), (LENGTH_TWO_LOOP, measure, dfg.frequency(source, target))
                )

    if connect_all:
        _connect_all_activities(dfg, admitted)

    rows = [(s, t, kind, measure, n) for (s, t), (kind, measure, n) in admitted.items()]
    edges = pd.DataFrame(rows, columns=list(MODEL_EDGE_COLUMNS))
    return HeuristicNet(
        activities=dict(dfg.activity_counts),
        start_activities=dict(dfg.start_activities),
        end_activities=dict(dfg.end_activities),
        edges=edges.sort_values([SOURCE, TARGET], kind="stable").reset_index(drop=True),
        threshold=threshold,
        case_count=dfg.case_count,
    )


def _connect_all_activities(
    dfg: DirectlyFollowsGraph, admitted: dict[tuple[str, str], tuple[str, float, int]]
) -> None:
    """Give activities lacking an incoming or outgoing edge their strongest observed one.

    Mutates `admitted`, visiting activities alphabetically so the result is deterministic. Start
    activities need no incoming edge and end activities no outgoing edge. Only pairs observed in
    the DFG are candidates; the highest dependency wins, then the higher frequency, then name order.
    The winning dependency can be low or even negative; the `best_connection` kind flags that the
    edge is there for connectivity, not because the threshold was met.
    """
    observed = [
        (source, target, int(frequency))
        for source, target, frequency in dfg.edges[[SOURCE, TARGET, FREQUENCY]].itertuples(
            index=False, name=None
        )
        if source != target
    ]

    def admit_strongest(candidates: list[tuple[str, str, int]]) -> None:
        """Admit the candidate with the highest dependency as a best connection, if any exist."""
        if not candidates:
            return
        source, target, frequency = min(
            candidates,
            key=lambda c: (-dependency_measure(c[2], dfg.frequency(c[1], c[0])), -c[2], c[0], c[1]),
        )
        dependency = dependency_measure(frequency, dfg.frequency(target, source))
        admitted[(source, target)] = (BEST_CONNECTION, dependency, frequency)

    for activity in sorted(dfg.activity_counts):
        if activity not in dfg.start_activities and not any(
            t == activity and s != t for s, t in admitted
        ):
            admit_strongest([c for c in observed if c[1] == activity])
        if activity not in dfg.end_activities and not any(
            s == activity and s != t for s, t in admitted
        ):
            admit_strongest([c for c in observed if c[0] == activity])


def format_summary(net: HeuristicNet) -> str:
    """Render the mined model's shape and its non-causal edges as plain text.

    Why loop and best-connection edges are listed one by one: they are the edges a reviewer should
    question first. Loops point at rework, and best connections exist only for connectivity.
    """
    kinds = net.edges[KIND].value_counts()
    rule_counts = ", ".join(
        f"{kind} {int(kinds.get(kind, 0))}"
        for kind in (CAUSAL, LENGTH_ONE_LOOP, LENGTH_TWO_LOOP, BEST_CONNECTION)
    )
    lines = [
        f"Threshold: {net.threshold}   Cases: {net.case_count:,}   "
        f"Activities: {len(net.activities)}   Edges: {len(net.edges)}",
        f"Edges by rule: {rule_counts}",
        f"Start activities: {net.start_activities}",
        f"Orphan activities: {', '.join(net.orphan_activities) or 'none'}",
    ]
    special = net.edges[net.edges[KIND] != CAUSAL]
    if not special.empty:
        lines.append("Loop and connectivity edges:")
        lines += [
            f"  {edge.source} -> {edge.target} [{edge.kind}] "
            f"measure {edge.dependency:.3f}, frequency {edge.frequency:,}"
            for edge in special.itertuples()
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: `python -m meridian.discovery.heuristic_miner [--threshold T]`.

    Reads the normalized log written by ingestion, writes `heuristic_net.json`, and prints a
    summary. The threshold defaults to the configured value so a run is reproducible from the
    environment alone, and an explicit flag makes threshold experiments one command each.
    """
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Mine the heuristic process model (Module A).")
    parser.add_argument(
        "--threshold",
        type=float,
        default=settings.dependency_threshold,
        help="dependency threshold strictly between 0 and 1 (default: configured value, 0.9)",
    )
    parser.add_argument(
        "--no-connect-all",
        action="store_true",
        help="skip the all-activities-connected heuristic",
    )
    args = parser.parse_args(argv)

    try:
        validate_dependency_threshold(args.threshold)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    if not settings.event_log_csv.exists():
        print(
            f"No normalized event log at {settings.event_log_csv}; "
            "run `python -m meridian.ingestion` first.",
            file=sys.stderr,
        )
        return 1

    net = mine_heuristic_net(
        read_event_log_csv(settings.event_log_csv),
        args.threshold,
        connect_all=not args.no_connect_all,
    )
    settings.heuristic_net_json.write_text(json.dumps(net.to_dict(), indent=2) + "\n")
    print(format_summary(net))
    print(f"Model written to {settings.heuristic_net_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
