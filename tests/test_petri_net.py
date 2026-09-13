"""Tests for the labelled Petri net and the sequence-net builder."""

import pytest

from meridian.conformance.petri_net import PetriNet, Transition, sequence_net


def test_sequence_net_chains_places_and_transitions() -> None:
    """A, B, C becomes p0 -A-> p1 -B-> p2 -C-> p3, starting in p0 and ending in p3."""
    net = sequence_net(["A", "B", "C"])

    assert net.places == ("p0", "p1", "p2", "p3")
    assert [(t.label, t.inputs, t.outputs) for t in net.transitions] == [
        ("A", ("p0",), ("p1",)),
        ("B", ("p1",), ("p2",)),
        ("C", ("p2",), ("p3",)),
    ]
    assert dict(net.initial_marking) == {"p0": 1}
    assert dict(net.final_marking) == {"p3": 1}
    assert net.labels == frozenset({"A", "B", "C"})


def test_repeated_activities_get_distinct_transitions_in_order() -> None:
    """A reference may require an activity twice; lookups return both, earliest first."""
    net = sequence_net(["A", "B", "A"])

    assert [t.id for t in net.transitions_for("A")] == ["t0", "t2"]
    assert net.transitions_for("Z") == ()


def test_empty_sequence_is_rejected() -> None:
    """A model with no steps cannot be replayed against."""
    with pytest.raises(ValueError, match="at least one activity"):
        sequence_net([])


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"transitions": (Transition("t0", "A", ("p0",), ("missing",)),)},
            "unknown places",
        ),
        (
            {
                "transitions": (
                    Transition("t0", "A", ("p0",), ("p1",)),
                    Transition("t0", "B", ("p0",), ("p1",)),
                )
            },
            "duplicate transition ids",
        ),
        ({"places": ("p0", "p0", "p1")}, "duplicate place names"),
        ({"initial_marking": {"p0": 0}}, "at least one token"),
        ({"final_marking": {"p1": -1}}, "negative token count"),
        ({"final_marking": {"nowhere": 1}}, "unknown places"),
    ],
)
def test_structurally_broken_nets_are_rejected(kwargs: dict, message: str) -> None:
    """Replay relies on a valid net, so invalid structure fails at construction, not mid-replay."""
    base = {
        "places": ("p0", "p1"),
        "transitions": (Transition("t0", "A", ("p0",), ("p1",)),),
        "initial_marking": {"p0": 1},
        "final_marking": {"p1": 1},
    }

    with pytest.raises(ValueError, match=message):
        PetriNet(**(base | kwargs))
