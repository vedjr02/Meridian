"""Tests for the layered process-map layout."""

from meridian.discovery.layout import (
    LAYER_SPACING,
    ROW_SPACING,
    NodePosition,
    count_crossings,
    layered_layout,
)

CHAIN_WITH_BRANCH = [("S", "A"), ("A", "B"), ("A", "C"), ("B", "E"), ("C", "E")]


def test_layers_follow_distance_from_start() -> None:
    """S is stage 0, A stage 1, B and C stage 2, E stage 3."""
    layout = layered_layout("SABCE", CHAIN_WITH_BRANCH, ["S"])

    assert {node: layout[node].layer for node in "SABCE"} == {
        "S": 0,
        "A": 1,
        "B": 2,
        "C": 2,
        "E": 3,
    }


def test_coordinates_are_spaced_and_centred_per_layer() -> None:
    """X steps by layer; a layer's rows are centred on y = 0."""
    layout = layered_layout("SABCE", CHAIN_WITH_BRANCH, ["S"])

    assert layout["E"].x == 3 * LAYER_SPACING
    assert (layout["S"].y, layout["A"].y) == (0.0, 0.0)
    assert sorted((layout["B"].y, layout["C"].y)) == [-ROW_SPACING / 2, ROW_SPACING / 2]


def test_back_edges_and_self_loops_do_not_move_activities_right() -> None:
    """Rework (B -> A) and repetition (B -> B) must not change the forward stages."""
    edges = CHAIN_WITH_BRANCH + [("B", "A"), ("B", "B"), ("E", "S")]

    layout = layered_layout("SABCE", edges, ["S"])

    assert [layout[node].layer for node in "SABE"] == [0, 1, 2, 3]


def test_unreachable_activity_gets_its_own_final_layer() -> None:
    """An activity no start can reach stays visible after the last stage."""
    layout = layered_layout("SABCEZ", CHAIN_WITH_BRANCH, ["S"])

    assert layout["Z"].layer == 4


def test_ordering_removes_an_avoidable_crossing() -> None:
    """Alphabetical order puts X above Y, crossing A->Y and B->X; barycenter ordering fixes it."""
    edges = [("S", "A"), ("S", "B"), ("A", "Y"), ("B", "X")]
    naive = {"S": (0, 0), "A": (1, 0), "B": (1, 1), "X": (2, 0), "Y": (2, 1)}
    naive_positions = {
        node: NodePosition(node, layer, order, 0.0, 0.0) for node, (layer, order) in naive.items()
    }
    assert count_crossings(naive_positions, edges) == 1

    layout = layered_layout("SABXY", edges, ["S"])

    assert count_crossings(layout, edges) == 0


def test_layout_is_independent_of_input_order() -> None:
    """The same graph given in any order must be drawn identically."""
    forward = layered_layout("SABCE", CHAIN_WITH_BRANCH, ["S"])
    backward = layered_layout("ECBAS", list(reversed(CHAIN_WITH_BRANCH)), ["S"])

    assert forward == backward
