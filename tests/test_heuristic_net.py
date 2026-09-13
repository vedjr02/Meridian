"""Tests for the assembled heuristic process model: loops, connectivity and output shape.

Expected edges are derived by hand from `LOOP_VARIANTS`; the arithmetic sits next to each one.
"""

import json

import pytest
from test_heuristic_miner import log_from_variants

from meridian.discovery.dfg import build_dfg
from meridian.discovery.heuristic_miner import (
    BEST_CONNECTION,
    CAUSAL,
    LENGTH_ONE_LOOP,
    LENGTH_TWO_LOOP,
    MODEL_EDGE_COLUMNS,
    Relation,
    footprint_matrix,
    mine_heuristic_net,
)

LOOP_VARIANTS = {
    ("S", "A", "B", "E"): 20,
    ("S", "A", "B", "A", "B", "E"): 10,  # one A,B,A and one B,A,B per case
    ("S", "C", "C", "C", "E"): 5,  # C repeats itself: C>C twice per case
}
LOG = log_from_variants(LOOP_VARIANTS)

# DFG: S>A 30, A>B 40, B>A 10, B>E 30, S>C 5, C>C 10, C>E 5. Patterns: A,B,A 10, B,A,B 10.
EXPECTED = {
    ("S", "A"): (CAUSAL, 30 / 31),
    ("A", "B"): (LENGTH_TWO_LOOP, 20 / 21),  # pairwise (40-10)/51 = 0.59 alone would miss it
    ("B", "A"): (LENGTH_TWO_LOOP, 20 / 21),
    ("B", "E"): (CAUSAL, 30 / 31),
    ("C", "C"): (LENGTH_ONE_LOOP, 10 / 11),
    ("S", "C"): (BEST_CONNECTION, 5 / 6),  # 0.83 < 0.9, kept so C is not orphaned
    ("C", "E"): (BEST_CONNECTION, 5 / 6),
}


def _edges_by_pair(net) -> dict[tuple[str, str], tuple[str, float]]:
    """Index model edges by (source, target) as (kind, measure)."""
    return {(e.source, e.target): (e.kind, e.dependency) for e in net.edges.itertuples()}


def test_model_edges_kinds_and_measures_match_hand_derivation() -> None:
    """Causal edges, both loop kinds and best connections, each with its admitting measure."""
    net = mine_heuristic_net(LOG)

    assert tuple(net.edges.columns) == MODEL_EDGE_COLUMNS
    edges = _edges_by_pair(net)
    assert set(edges) == set(EXPECTED)
    for pair, (kind, measure) in EXPECTED.items():
        assert edges[pair][0] == kind, pair
        assert edges[pair][1] == pytest.approx(measure), pair


def test_length_two_loop_is_read_as_parallel_without_loop_detection() -> None:
    """The reason loop detection exists: the footprint alone calls the A,B loop parallel."""
    assert footprint_matrix(build_dfg(LOG)).loc["A", "B"] == Relation.PARALLEL
    assert _edges_by_pair(mine_heuristic_net(LOG))[("B", "A")][0] == LENGTH_TWO_LOOP


def test_existing_causal_direction_is_kept_when_a_loop_is_found() -> None:
    """A dominant A->B stays causal; the loop only adds the return edge B->A.

    A>B = 100 + 10 = 110, B>A = 5, so pairwise (110-5)/116 = 0.905 is causal; A,B,A 5 and B,A,B 5
    give (5+5)/11 = 0.909, a loop, which admits B->A.
    """
    log = log_from_variants({("S", "A", "B", "E"): 100, ("S", "A", "B", "A", "B", "E"): 5})

    edges = _edges_by_pair(mine_heuristic_net(log))

    assert edges[("A", "B")][0] == CAUSAL
    assert edges[("B", "A")] == (LENGTH_TWO_LOOP, pytest.approx(10 / 11))


def test_rare_return_pattern_is_not_a_loop() -> None:
    """One A,B,A in 30 cases scores (1+0)/2 = 0.5: noise, not a loop."""
    log = log_from_variants({("S", "A", "B", "E"): 29, ("S", "A", "B", "A", "E"): 1})

    kinds = {kind for kind, _ in _edges_by_pair(mine_heuristic_net(log)).values()}

    assert LENGTH_TWO_LOOP not in kinds


def test_without_connect_all_a_weakly_linked_activity_is_orphaned() -> None:
    """Turning the heuristic off shows why it exists: C keeps only its self-loop."""
    assert mine_heuristic_net(LOG).orphan_activities == []
    assert mine_heuristic_net(LOG, connect_all=False).orphan_activities == ["C"]


def test_start_end_and_metadata() -> None:
    """Start and end activities come straight from the log; the threshold used is recorded."""
    net = mine_heuristic_net(LOG, threshold=0.9)

    assert net.start_activities == {"S": 35}
    assert net.end_activities == {"E": 35}
    assert net.case_count == 35
    assert net.threshold == 0.9


def test_to_dict_is_json_serialisable_and_complete() -> None:
    """The model file is what the frontend renders, so every edge must survive serialisation."""
    net = mine_heuristic_net(LOG)

    payload = json.loads(json.dumps(net.to_dict()))

    assert len(payload["edges"]) == len(EXPECTED)
    assert payload["start_activities"] == {"S": 35}
    assert {"source", "target", "kind", "dependency", "frequency"} == set(payload["edges"][0])


def test_mining_is_deterministic() -> None:
    """Re-running on the same data must give identical output (02-TECH-STACK reproducibility)."""
    first = mine_heuristic_net(LOG).to_dict()
    second = mine_heuristic_net(LOG.sample(frac=1.0, random_state=11)).to_dict()

    assert first == second
